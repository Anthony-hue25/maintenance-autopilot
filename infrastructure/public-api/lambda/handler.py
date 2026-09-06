"""Public API boundary for the competition Demo Property.

The canonical Demo Property is intentionally U4 with $200 autonomous authority.
Only the maintenance report crosses the public boundary; all property and AWS
invocation configuration is trusted server-side state.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, ReadTimeoutError

LOG = logging.getLogger()
LOG.setLevel(logging.INFO)

DEMO_UNIT = os.environ.get("DEMO_PROPERTY_UNIT", "U4")
AUTHORITY_USD = int(os.environ.get("DEMO_PROPERTY_AUTHORITY_USD", "200"))
MAX_REPORT_LENGTH = int(os.environ.get("MAX_REPORT_LENGTH", "4000"))
MAX_BODY_BYTES = 8_192
RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
REGION = os.environ.get("AWS_AGENTCORE_REGION", "us-east-1")
SDK_READ_TIMEOUT_SECONDS = 25
INVOCATION_BUDGET_SECONDS = 26.5

OUTCOMES = {"ACT", "ASK", "AWAITING", "ESCALATE", "ACT+ESCALATE", "CLOSE"}
RULES = {
    "P00H_UNMAPPED_HAZARD", "P01_UNKNOWN_UNIT_CRITICAL", "P02_UNKNOWN_UNIT",
    "P03_CRITICAL_HAZARD", "P03S_PRIMARY_ENTRANCE_SECURITY_EXPOSURE",
    "P03S_SECURITY_EXPOSURE", "P04_AUTHORITY_EXCEEDED", "P05_SECURITY_SILENCE",
    "P05A_SECURITY_CLARIFICATION", "P06_NONSAFETY_SILENCE",
    "P07_NEEDS_CLARIFICATION", "P08_INSUFFICIENT_AFTER_ASK",
    "P00C_UNMAPPED_CONDITION", "P09_REPEAT_FAILURE", "P10_REPLACEMENT_UPGRADE",
    "P11_PROPERTY_DAMAGE", "P12_MOLD_SPREAD", "P12A_PROGRESSIVE_SCOPE",
    "P13_MATERIAL_MOISTURE_DAMAGE", "P14_RESOLVED",
    "P15_ROUTINE_AUTHORIZED_ACTION",
}

PRESENTATION = {
    "ACT": ("Authorized to proceed", "Within configured maintenance authority"),
    "ASK": ("One detail needed", "A focused clarification is required"),
    "AWAITING": ("Waiting for information", "The decision remains paused"),
    "ESCALATE": ("Landlord decision required", "Human authorization or judgment is required"),
    "ACT+ESCALATE": ("Protective action required", "Escalate for human oversight"),
    "CLOSE": ("No further action required", "No outstanding maintenance need remains"),
}

TRANSIENT_CODES = {
    "InternalServerException", "ServiceUnavailableException", "ThrottlingException",
    "TooManyRequestsException", "RetryableConflictException",
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _client(read_timeout: float = SDK_READ_TIMEOUT_SECONDS):
    return boto3.client(
        "bedrock-agentcore",
        region_name=REGION,
        config=Config(
            connect_timeout=3,
            read_timeout=read_timeout,
            retries={"max_attempts": 0},
        ),
    )


def _response(status: int, body: dict[str, Any], request_id: str) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json; charset=utf-8",
            "cache-control": "no-store",
            "x-content-type-options": "nosniff",
            "x-request-id": request_id,
        },
        "body": json.dumps(body, separators=(",", ":")),
    }


def _parse_request(event: dict[str, Any]) -> str:
    method = event.get("requestContext", {}).get("http", {}).get("method")
    if method and method != "POST":
        raise ApiError(405, "method_not_allowed", "Only POST is supported.")

    headers = {
        str(k).lower(): str(v)
        for k, v in (event.get("headers") or {}).items()
    }
    content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise ApiError(
            415,
            "unsupported_media_type",
            "Content-Type must be application/json.",
        )

    raw = event.get("body")
    if not isinstance(raw, str):
        raise ApiError(400, "malformed_json", "Request body must be valid JSON.")

    if event.get("isBase64Encoded"):
        try:
            raw_bytes = base64.b64decode(raw, validate=True)
            raw = raw_bytes.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            raise ApiError(
                400,
                "malformed_json",
                "Request body must be valid JSON.",
            )

    if len(raw.encode("utf-8")) > MAX_BODY_BYTES:
        raise ApiError(413, "payload_too_large", "Request body is too large.")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ApiError(400, "malformed_json", "Request body must be valid JSON.")

    if not isinstance(data, dict):
        raise ApiError(400, "invalid_request", "Request body must be a JSON object.")

    if set(data) != {"report"}:
        raise ApiError(
            400,
            "invalid_request",
            "Request body must contain only the report field.",
        )

    report = data.get("report")
    if not isinstance(report, str):
        raise ApiError(400, "invalid_report", "Report must be a string.")

    report = report.strip()
    if not report:
        raise ApiError(400, "invalid_report", "Report cannot be empty.")

    if len(report) > MAX_REPORT_LENGTH:
        raise ApiError(
            413,
            "report_too_long",
            f"Report must be {MAX_REPORT_LENGTH} characters or fewer.",
        )

    return report


def _read_runtime_body(response: dict[str, Any]) -> dict[str, Any]:
    body = response.get("response") or response.get("body")

    if hasattr(body, "read"):
        body = body.read()

    if isinstance(body, bytes):
        body = body.decode("utf-8")

    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("AgentCore returned malformed JSON") from exc

    if not isinstance(body, dict):
        raise ValueError("AgentCore returned an unrecognized response")

    return body


def _invoke(
    payload: dict[str, str],
    deadline: float | None = None,
) -> tuple[dict[str, Any], str]:
    if not RUNTIME_ARN:
        raise RuntimeError("AGENT_RUNTIME_ARN is not configured")

    deadline = (
        deadline
        if deadline is not None
        else time.monotonic() + INVOCATION_BUDGET_SECONDS
    )

    session_id = f"maint-{uuid.uuid4().hex}-{uuid.uuid4().hex}"[:64]
    last_error: Exception | None = None

    for attempt in range(2):
        remaining = deadline - time.monotonic()

        if remaining <= 0.5:
            raise TimeoutError(
                "AgentCore invocation exceeded its overall deadline"
            ) from last_error

        try:
            # A retry consumes the original invocation budget. It never receives a
            # fresh 25-second timeout after the first attempt has used that time.
            response = _client(
                min(SDK_READ_TIMEOUT_SECONDS, max(0.5, remaining))
            ).invoke_agent_runtime(
                agentRuntimeArn=RUNTIME_ARN,
                runtimeSessionId=session_id,
                contentType="application/json",
                accept="application/json",
                payload=json.dumps(payload).encode("utf-8"),
            )

            metadata = response.get("ResponseMetadata", {})
            return (
                _read_runtime_body(response),
                str(metadata.get("RequestId", "")),
            )

        except ReadTimeoutError as exc:
            raise TimeoutError("AgentCore invocation timed out") from exc

        except ClientError as exc:
            last_error = exc
            error = exc.response.get("Error", {})
            code = error.get("Code", "")
            message = error.get("Message", "")

            runtime_5xx = (
                code == "RuntimeClientError"
                and "Received error (5" in message
            )

            if (
                code not in TRANSIENT_CODES
                and not runtime_5xx
            ) or attempt == 1:
                raise

        except BotoCoreError as exc:
            last_error = exc

            if attempt == 1:
                raise

        backoff = 0.15 + random.random() * 0.15

        if deadline - time.monotonic() <= backoff + 0.5:
            raise TimeoutError(
                "AgentCore invocation exceeded its overall deadline"
            ) from last_error

        time.sleep(backoff)

    raise last_error or RuntimeError("AgentCore invocation failed")


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str)
        for item in value
    ):
        raise ValueError(f"Invalid {field}")

    return value


def _explanation(outcome: str, rule: str, hazards: list[str]) -> str:
    if (
        outcome == "ACT+ESCALATE"
        and rule == "P03_CRITICAL_HAZARD"
        and any("GAS" in h for h in hazards)
    ):
        return (
            "Autopilot identified a credible gas hazard. Protective action can "
            "proceed without waiting for approval, while human involvement is "
            "required."
        )

    return {
        "ACT": (
            "The report is within configured authority and no deterministic "
            "escalation rule applies."
        ),
        "ASK": (
            "A decision-changing detail is missing, so one focused clarification "
            "is required."
        ),
        "AWAITING": (
            "The required information has not been received, so the decision "
            "remains paused."
        ),
        "ESCALATE": (
            "The report exceeds autonomous authority or requires landlord judgment."
        ),
        "ACT+ESCALATE": (
            "Immediate protective action is warranted while a human provides "
            "oversight."
        ),
        "CLOSE": (
            "The returned facts indicate no outstanding maintenance need."
        ),
    }[outcome]


def _normalize(
    raw: dict[str, Any],
    evaluation_id: str,
    created_at: str,
    aws_request_id: str,
    latency_ms: int,
) -> dict[str, Any]:
    outcome = raw.get("PolicyOutcome")
    rule = raw.get("PolicyRule")

    if outcome not in OUTCOMES or rule not in RULES:
        raise ValueError("Unknown or missing policy outcome/rule")

    hazards = _string_list(raw.get("HazardConcepts"), "HazardConcepts")
    conditions = _string_list(raw.get("ConditionConcepts"), "ConditionConcepts")
    information = raw.get("InformationState")
    urgency = raw.get("Predicted_Urgency")
    trade = raw.get("Predicted_PrimaryTrade")

    if not all(
        isinstance(value, str) and value
        for value in (information, urgency, trade)
    ):
        raise ValueError(
            "AgentCore response is missing required technical facts"
        )

    headline, subheadline = PRESENTATION[outcome]

    boundary = {
        "ACT": (
            f"Within the Demo Property's configured ${AUTHORITY_USD} autonomous "
            "authority; this is authority context, not an estimated repair cost."
        ),
        "ASK": "A decision-changing fact is still required.",
        "AWAITING": "Awaiting the requested information.",
        "ESCALATE": (
            "Outside autonomous authority or requires owner judgment."
        ),
        "ACT+ESCALATE": (
            "Protective action may proceed; human oversight is required."
        ),
        "CLOSE": "No outstanding need remains.",
    }[outcome]

    next_action = {
        "ACT": "Proceed with the authorized maintenance next action.",
        "ASK": "Request one focused clarification.",
        "AWAITING": "Wait for the requested information.",
        "ESCALATE": "Refer the decision to the landlord.",
        "ACT+ESCALATE": (
            "Take protective action and escalate for oversight."
        ),
        "CLOSE": "Close the report without further maintenance action.",
    }[outcome]

    situation = "; ".join(hazards + conditions) or "Maintenance report evaluated"

    return {
        "evaluation_id": evaluation_id,
        "created_at": created_at,
        "decision": outcome,
        "policy_rule": rule,
        "presentation": {
            "headline": headline,
            "subheadline": subheadline,
            "explanation": _explanation(outcome, rule, hazards),
        },
        "trace": {
            "situation": situation,
            "boundary": boundary,
            "next_action": next_action,
        },
        "technical": {
            "hazard": hazards,
            "information": information,
            "urgency": urgency,
            "trade": trade,
        },
        "runtime": {
            "request_id": aws_request_id,
            "latency_ms": latency_ms,
        },
    }


def lambda_handler(
    event: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
    correlation_id = (
        getattr(context, "aws_request_id", None)
        or str(uuid.uuid4())
    )
    started = time.monotonic()

    try:
        report = _parse_request(event)

        evaluation_id = f"eval_{uuid.uuid4().hex}"
        case_id = f"CASE-{uuid.uuid4().hex}"
        created_at = (
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

        LOG.info(
            "evaluation_started correlation_id=%s evaluation_id=%s "
            "case_id=%s report_sha256=%s report_length=%d",
            correlation_id,
            evaluation_id,
            case_id,
            hashlib.sha256(report.encode()).hexdigest()[:12],
            len(report),
        )

        raw, aws_request_id = _invoke(
            {
                "request": report,
                "unit": DEMO_UNIT,
                "clarification": "",
                "case_id": case_id,
            },
            deadline=started + INVOCATION_BUDGET_SECONDS,
        )

        latency_ms = round(
            (time.monotonic() - started) * 1000
        )

        normalized = _normalize(
            raw,
            evaluation_id,
            created_at,
            aws_request_id,
            latency_ms,
        )

        LOG.info(
            "evaluation_completed correlation_id=%s evaluation_id=%s "
            "outcome=%s rule=%s latency_ms=%d agentcore_request_id=%s",
            correlation_id,
            evaluation_id,
            normalized["decision"],
            normalized["policy_rule"],
            latency_ms,
            aws_request_id,
        )

        return _response(
            200,
            normalized,
            correlation_id,
        )

    except ApiError as exc:
        return _response(
            exc.status,
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
                "request_id": correlation_id,
            },
            correlation_id,
        )

    except TimeoutError:
        LOG.warning(
            "evaluation_timeout correlation_id=%s",
            correlation_id,
        )

        return _response(
            504,
            {
                "error": {
                    "code": "runtime_timeout",
                    "message": (
                        "The live evaluation timed out. "
                        "Please try again."
                    ),
                },
                "request_id": correlation_id,
            },
            correlation_id,
        )

    except (ClientError, BotoCoreError):
        LOG.exception(
            "agentcore_invocation_failed correlation_id=%s",
            correlation_id,
        )

        return _response(
            502,
            {
                "error": {
                    "code": "runtime_unavailable",
                    "message": (
                        "The live evaluation service is temporarily unavailable."
                    ),
                },
                "request_id": correlation_id,
            },
            correlation_id,
        )

    except Exception:
        LOG.exception(
            "evaluation_failed correlation_id=%s",
            correlation_id,
        )

        return _response(
            502,
            {
                "error": {
                    "code": "invalid_runtime_response",
                    "message": (
                        "The live evaluation returned an unusable response."
                    ),
                },
                "request_id": correlation_id,
            },
            correlation_id,
        )