import json

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from runtime_adapter import MaintenanceAutopilotRuntime

app = BedrockAgentCoreApp()
log = app.logger

runtime = MaintenanceAutopilotRuntime()


def _get_string(payload, key, default=""):
    value = payload.get(key, default)

    if value is None:
        return default

    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")

    return value.strip()


def _normalize_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")

    # Direct structured invocation:
    # {
    #   "request": "...",
    #   "unit": "U4",
    #   "clarification": "",
    #   "case_id": "..."
    # }
    if "request" in payload:
        return payload

    # AgentCore CLI invocation:
    # {
    #   "prompt": "{\"request\":\"...\",\"unit\":\"U4\",...}"
    # }
    prompt = payload.get("prompt")

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError(
            "payload must contain either 'request' or a non-empty 'prompt' string"
        )

    try:
        decoded = json.loads(prompt)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "prompt must contain a JSON object with a 'request' field"
        ) from exc

    if not isinstance(decoded, dict):
        raise ValueError("prompt JSON must be an object")

    return decoded


@app.entrypoint
def invoke(payload, context):
    payload = _normalize_payload(payload)

    request = _get_string(payload, "request")
    if not request:
        raise ValueError("request must be a non-empty string")

    unit = _get_string(payload, "unit")
    clarification = _get_string(payload, "clarification")
    case_id = _get_string(payload, "case_id", "LIVE") or "LIVE"

    log.info("Maintenance Autopilot invocation: case_id=%s", case_id)

    return runtime.evaluate(
        request=request,
        unit=unit,
        clarification=clarification,
        case_id=case_id,
    )


if __name__ == "__main__":
    app.run()