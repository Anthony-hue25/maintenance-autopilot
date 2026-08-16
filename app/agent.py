import csv
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from strands import Agent
from strands.models import BedrockModel

from app.tools import (
    PROPERTIES,
    get_property_details,
    check_repair_authority,
    screen_identity,
    screen_safety,
    screen_information_state,
    screen_scope_change,
    screen_replacement_upgrade,
    screen_security_information,
    screen_resolution_state,
    screen_repeat_failure,
)


GROUND_TRUTH_PATH = Path("data/ground_truth.csv")
PREDICTIONS_PATH = Path("data/agent_predictions.csv")

# None = run the complete regression benchmark.
# Replace with a list of Case_ID strings to run a subset.
RUN_CASE_IDS = None


TradeCategory = Literal[
    "PLUMBING",
    "HVAC",
    "ELECTRICAL",
    "APPLIANCE",
    "LOCKSMITH",
    "GENERAL",
    "PEST",
    "STRUCTURAL",
    "MOISTURE",
    "GAS",
    "NONE",
    "UNKNOWN",
]


class MaintenanceDecision(BaseModel):
    Case_ID: str

    Safety: Literal[
        "Safe",
        "Unsafe",
        "Unknown",
        "Uncertain",
        "Potential concern",
    ]

    Urgency: Literal[
        "Emergency",
        "Priority",
        "Routine",
        "Cosmetic",
        "None",
        "Unknown",
    ]

    PrimaryTrade: TradeCategory

    SecondaryTrades: list[TradeCategory] = Field(
        default_factory=list
    )

    Outcome: Literal[
        "ACT",
        "ESCALATE",
        "AWAITING",
        "CLOSE",
        "ASK",
        "ACT+ESCALATE",
    ]

    Reason: str


SYSTEM_PROMPT = """
You are Maintenance Autopilot.

Evaluate ONE rental-maintenance case independently.

Use the property and authority tools whenever relevant.

Reason carefully about:
- safety,
- urgency,
- trade,
- authority,
- scope,
- replacement,
- maintenance history,
- information sufficiency,
- and whether owner judgment is required.

Do not invent facts.

Return structured output only.
"""


def load_cases():
    with GROUND_TRUTH_PATH.open(
        newline="",
        encoding="utf-8",
    ) as file:
        rows = list(csv.DictReader(file))

    if RUN_CASE_IDS is None:
        return rows

    rows_by_id = {
        row["Case_ID"]: row
        for row in rows
    }

    missing = [
        case_id
        for case_id in RUN_CASE_IDS
        if case_id not in rows_by_id
    ]

    if missing:
        raise ValueError(
            f"Missing case IDs: {missing}"
        )

    return [
        rows_by_id[case_id]
        for case_id in RUN_CASE_IDS
    ]


def build_guardrails(row):
    request = row["Request"]
    clarification = row["Clarification_Response"]

    unit_data = PROPERTIES.get(
        row["Unit"],
        {}
    )

    history = unit_data.get(
        "history",
        ""
    )

    return {
        "identity": screen_identity(
            row["Unit"]
        ),

        "safety": screen_safety(
            request,
            clarification,
        ),

        "information": screen_information_state(
            request,
            clarification,
        ),

        "scope": screen_scope_change(
            request,
            clarification,
        ),

        "replacement": screen_replacement_upgrade(
            request,
            clarification,
        ),

        "security": screen_security_information(
            request,
            clarification,
        ),

        "resolution": screen_resolution_state(
            request,
            clarification,
        ),

        "repeat": screen_repeat_failure(
            request,
            clarification,
            history,
        ),
    }


def build_case_prompt(row, guardrails):
    clarification = (
        row["Clarification_Response"]
        if row["Clarification_Response"].strip()
        else "None provided"
    )

    return f"""
Case_ID: {row['Case_ID']}
Unit: {row['Unit']}

Request:
{row['Request']}

Clarification:
{clarification}

Deterministic guardrails:
{guardrails}

Use property and authority tools when relevant.

Return the structured decision.
"""


def resolve_outcome(
    row,
    decision,
    guardrails,
):
    """
    Deterministic enforcement of the frozen outcome rules.

    This function may override Outcome only.
    Safety, Urgency, PrimaryTrade and SecondaryTrades remain
    the raw agent classifications.
    """

    identity = guardrails["identity"]
    safety = guardrails["safety"]
    information = guardrails["information"]
    scope = guardrails["scope"]
    replacement = guardrails["replacement"]
    security = guardrails["security"]
    resolution = guardrails["resolution"]
    repeat = guardrails["repeat"]

    request_text = row["Request"].lower()

    strong_emergency_hazards = {
        "GAS_OR_CO",
        "ELECTRICAL_OR_FIRE",
        "WATER_NEAR_ELECTRICAL",
        "UNCONTROLLED_WATER",
    }

    strong_emergency = bool(
        strong_emergency_hazards.intersection(
            set(safety["hazards"])
        )
    )

    # -------------------------------------------------
    # DECISION 0 — IDENTITY
    # -------------------------------------------------

    if identity["identity_problem"]:
        if strong_emergency:
            return "ACT+ESCALATE"

        return "ESCALATE"

    # -------------------------------------------------
    # SAFETY / EMERGENCY
    # -------------------------------------------------

    if strong_emergency:
        return "ACT+ESCALATE"

    if "STRUCTURAL_OR_FALL" in safety["hazards"]:
        return "ACT+ESCALATE"

    # -------------------------------------------------
    # SECURITY INFORMATION
    # -------------------------------------------------

    if security["safety_silence"]:
        return "ACT"

    if security["needs_clarification"]:
        return "ASK"

    # -------------------------------------------------
    # GENERAL INFORMATION
    # -------------------------------------------------

    if information["needs_initial_clarification"]:
        return "ASK"

    if information["no_response_after_ask"]:
        return "AWAITING"

    if information["insufficient_after_ask"]:
        return "ESCALATE"

    # -------------------------------------------------
    # REPEAT FAILURE
    # -------------------------------------------------

    if repeat["repeat_failure_detected"]:
        return "ESCALATE"

    # -------------------------------------------------
    # REPLACEMENT / UPGRADE
    # -------------------------------------------------

    if replacement["replacement_or_upgrade"]:
        return "ESCALATE"

    # -------------------------------------------------
    # SMOKE ALARM CHIRP
    # -------------------------------------------------

    smoke_alarm_chirp = (
        "smoke alarm" in request_text
        and "chirp" in request_text
        and "fire" not in request_text
        and "burning" not in request_text
        and "smoke coming" not in request_text
        and "visible smoke" not in request_text
    )

    if smoke_alarm_chirp:
        return "ACT"

    # -------------------------------------------------
    # PROPERTY DAMAGE
    # -------------------------------------------------

    if scope["property_damage_detected"]:
        return "ACT+ESCALATE"

    # -------------------------------------------------
    # MOLD / MATERIAL SCOPE CHANGE
    # -------------------------------------------------

    if scope["mold_scope_detected"]:
        return "ESCALATE"

    if scope["scope_change_detected"]:
        return "ESCALATE"

    # -------------------------------------------------
    # RESOLUTION
    # -------------------------------------------------

    if resolution["close_candidate"]:
        return "CLOSE"

    # Otherwise preserve the raw model decision.
    return decision.Outcome


def main():
    model = BedrockModel(
        model_id="us.amazon.nova-2-lite-v1:0",
        region_name="us-east-1",
        temperature=0,
    )

    cases = load_cases()

    print(
        f"\nLoaded {len(cases)} benchmark cases."
    )

    predictions = []

    for index, row in enumerate(cases, start=1):
        print(
            f"\nEvaluating {row['Case_ID']} "
            f"({index}/{len(cases)})..."
        )

        guardrails = build_guardrails(row)

        # Fresh Strands agent for every benchmark case.
        # This prevents conversation history from leaking
        # between independent evaluation scenarios.
        agent = Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            tools=[
                get_property_details,
                check_repair_authority,
            ],
        )

        result = agent(
            build_case_prompt(
                row,
                guardrails,
            ),
            structured_output_model=MaintenanceDecision,
        )

        decision = result.structured_output

        if decision.Case_ID != row["Case_ID"]:
            raise ValueError(
                f"Expected {row['Case_ID']} "
                f"but agent returned {decision.Case_ID}"
            )

        raw_outcome = decision.Outcome

        governor_outcome = resolve_outcome(
            row,
            decision,
            guardrails,
        )

        governor_intervened = (
            raw_outcome != governor_outcome
        )

        predictions.append(
            {
                "Case_ID": decision.Case_ID,
                "Predicted_Safety": decision.Safety,
                "Predicted_Urgency": decision.Urgency,
                "Predicted_PrimaryTrade": decision.PrimaryTrade,
                "Predicted_SecondaryTrades": "|".join(
                    decision.SecondaryTrades
                ),
                "Raw_Agent_Outcome": raw_outcome,
                "Governor_Outcome": governor_outcome,
                "Governor_Intervened": governor_intervened,
                "Reason": decision.Reason,
            }
        )

        intervention_marker = (
            " [GOVERNOR]"
            if governor_intervened
            else ""
        )

        print(
            f"{decision.Case_ID}: "
            f"{decision.Safety} | "
            f"{decision.Urgency} | "
            f"{decision.PrimaryTrade} | "
            f"{decision.SecondaryTrades} | "
            f"RAW={raw_outcome} | "
            f"GOV={governor_outcome}"
            f"{intervention_marker}"
        )

    with PREDICTIONS_PATH.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "Case_ID",
                "Predicted_Safety",
                "Predicted_Urgency",
                "Predicted_PrimaryTrade",
                "Predicted_SecondaryTrades",
                "Raw_Agent_Outcome",
                "Governor_Outcome",
                "Governor_Intervened",
                "Reason",
            ],
        )

        writer.writeheader()
        writer.writerows(predictions)

    print(
        f"\nSaved {len(predictions)} predictions to "
        f"{PREDICTIONS_PATH}"
    )


if __name__ == "__main__":
    main()