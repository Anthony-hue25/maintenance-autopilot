import csv
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from strands import Agent
from strands.models import BedrockModel

from app.tools import (
    get_property_details,
    screen_safety,
    screen_information_state,
    screen_scope_change,
    screen_security_information,
    screen_resolution_state,
)


GROUND_TRUTH_PATH = Path("data/ground_truth.csv")
PREDICTIONS_PATH = Path("data/agent_predictions.csv")

TEST_CASE_IDS = [
    "GT-001",
    "GT-002",
    "GT-003",
    "GT-004",
    "GT-005",
    "GT-006",
    "GT-007",
    "GT-008",
    "GT-009",
    "GT-010",
    "GT-011",
    "GT-012",
    "GT-013",
    "GT-014",
    "GT-015",
    "GT-016",
    "GT-017",
    "GT-018",
    "GT-019",
    "GT-020",
    "GT-021",
    "GT-022A",
    "GT-022B",
    "GT-023",
    "GT-024",
    "GT-025",
    "GT-026",
    "GT-027",
    "GT-028",
    "GT-029",
    "GT-030",
    "GT-031",
    "GT-032",
    "GT-033",
    "GT-034",
    "GT-035",
    "GT-036",
    "GT-037",
    "GT-038",
    "GT-039",
    "GT-040",
    "GT-041",
    "GT-042",
    "GT-043",
    "GT-044",
    "GT-045",
    "GT-046",
    "GT-047",
    "GT-048",
    "GT-049",
    "GT-050",
    "GT-051",
    "GT-052",
    "GT-053",
    "GT-054",
    "GT-055",
    "GT-056",
    "GT-057",
    "GT-058",
    "GT-059",
    "GT-060",
]

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
        default_factory=list,
        description=(
            "Additional relevant trades. Use an empty list if none."
        ),
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

Evaluate ONE residential rental-maintenance case using the frozen
Maintenance Autopilot Decision Standard v1.3.

CORE PRINCIPLE
The agent asks to decide, not to know everything.

DECISION -1 — DECOMPOSE
If multiple distinct maintenance issues are reported, treat them
separately. Process the highest safety/urgency issue first.

DECISION 0 — PROPERTY CONTEXT
Use get_property_details whenever owner authority, history, equipment,
vendor, or access information could affect the decision.

Never infer property data.

If the unit cannot be identified, normal maintenance work must ESCALATE.
Emergency mitigation must not wait for identity.

DECISION 1 — SAFETY
Safety comes first.

Strong emergency signals include:
- gas or CO,
- smoke/fire,
- strong burning electrical smell,
- exposed electrical wiring,
- uncontrolled water,
- water in credible contact with electrical equipment.

Emergency means ACT+ESCALATE:
take protective action AND notify/escalate to the owner.

"Uncontrolled water" means water escaping containment or causing
active property-damage risk.

Water moving within a fixture, such as a toilet continuously filling
without overflowing, is NOT automatically uncontrolled water.

DECISION 2 — INFORMATION
Ask only for information that changes the NEXT decision.

Maximum one focused clarification round.

If the tenant responds but decision-critical information is still
insufficient -> ESCALATE.

If the tenant does not respond and no safety/security issue is open
-> AWAITING.

If the tenant does not respond and a safety/security question remains
open -> protective ACT.

DECISION 3 — URGENCY
Allowed:
Emergency
Priority
Routine
Cosmetic
None
Unknown

Read urgency from facts, not tone.

DECISION 4 — TRADE
Allowed:
PLUMBING
HVAC
ELECTRICAL
APPLIANCE
LOCKSMITH
GENERAL
PEST
STRUCTURAL
MOISTURE
GAS
NONE
UNKNOWN

Use PrimaryTrade for the next action.
Use SecondaryTrades only when another trade is genuinely relevant.

DECISION 5 — ACT
ACT means take the next authorized step.

It may mean:
dispatch,
diagnose,
schedule,
quote,
approve,
log,
defer,
bundle,
or protect.

Unknown repair cost does not block a diagnostic ACT.

SPEND AUTHORITY
The property-specific autonomous authority limit returned by
get_property_details is the controlling spend threshold.

There is NO separate "typical", "routine", default, or implied lower
spend threshold once the property-specific limit is known.

If quoted cost <= property authority limit AND no override applies:
ACT.

If quoted cost > property authority limit:
ESCALATE.

Do not invent additional approval thresholds.

DECISION 6 — ESCALATE
Escalate for:
- authority exceeded,
- significant uncertainty,
- repeat failure,
- material scope change,
- replacement/upgrade,
- structural,
- insurance,
- legal/regulatory implications.

REPEAT FAILURE
Repeat failure means the same or materially related failure mode.

Do NOT treat unrelated faults on the same fixture as repeat failure.

Examples:
- clog followed by clog -> repeat failure
- slow drain followed by slow drain -> repeat failure
- toilet clog followed by running fill valve -> NOT repeat failure

OVERRIDES
Safety risk
Significant uncertainty
Repeat failure
Material scope change
Replacement/upgrade

CLOSE
CLOSE means no outstanding maintenance need remains.

Do not invent preventive work on a resolved case.

GOLDEN RULE
Do not bring the owner a problem.
Bring the owner a decision.

Never invent costs, repair mechanisms, contractor findings,
authority limits, or property context.
"""


def load_cases():
    with GROUND_TRUTH_PATH.open(
        newline="",
        encoding="utf-8",
    ) as file:
        rows = list(csv.DictReader(file))

    cases_by_id = {
        row["Case_ID"]: row
        for row in rows
    }

    return [
        cases_by_id[case_id]
        for case_id in TEST_CASE_IDS
    ]


def build_case_prompt(row):
    clarification = (
        row["Clarification_Response"]
        if row["Clarification_Response"].strip()
        else "None provided"
    )

    safety_result = screen_safety(
        row["Request"],
        row["Clarification_Response"],
    )

    information_result = screen_information_state(
        row["Request"],
        row["Clarification_Response"],
    )

    scope_result = screen_scope_change(
        row["Request"],
        row["Clarification_Response"],
    )

    security_result = screen_security_information(
        row["Request"],
        row["Clarification_Response"],
    )

    resolution_result = screen_resolution_state(
        row["Request"],
        row["Clarification_Response"],
    )

    return f"""
Evaluate this case.

Case_ID: {row['Case_ID']}
Unit: {row['Unit']}

Request:
{row['Request']}

Clarification:
{clarification}

GUARDRAILS

Safety:
hazard_detected = {safety_result['hazard_detected']}
hazards = {safety_result['hazards']}

Information:
clarification_provided = {information_result['clarification_provided']}
insufficient_after_ask = {information_result['insufficient_after_ask']}
no_response_after_ask = {information_result['no_response_after_ask']}
signals = {information_result['signals']}

Scope:
scope_change_detected = {scope_result['scope_change_detected']}
signals = {scope_result['signals']}

Security:
security_issue = {security_result['security_issue']}
needs_clarification = {security_result['needs_clarification']}
safety_silence = {security_result['safety_silence']}
security_known = {security_result['security_known']}

Resolution:
resolved_signal = {resolution_result['resolved_signal']}
outstanding_signal = {resolution_result['outstanding_signal']}
close_candidate = {resolution_result['close_candidate']}

RULE APPLICATION

If no_response_after_ask is True:
- no safety/security issue open -> AWAITING
- safety/security question open -> protective ACT

If insufficient_after_ask is True:
- tenant responded but the case remains decision-critically unclear
- ESCALATE unless emergency action takes precedence

If scope_change_detected is True:
- treat material hidden damage or expanded scope as an escalation override

If close_candidate is True and no outstanding issue remains:
- CLOSE
- do not invent preventive inspection or work

If needs_clarification is True:
- ASK

If safety_silence is True:
- protective ACT

Use the property tool whenever authority, history, equipment,
vendor, or access affects the decision.

Return structured output only.
"""


def main():
    model = BedrockModel(
        model_id="us.amazon.nova-2-lite-v1:0",
        region_name="us-east-1",
        temperature=0,
    )

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[get_property_details],
    )

    predictions = []

    for row in load_cases():
        print(f"\nEvaluating {row['Case_ID']}...")

        result = agent(
            build_case_prompt(row),
            structured_output_model=MaintenanceDecision,
        )

        decision = result.structured_output

        predictions.append(
            {
                "Case_ID": decision.Case_ID,
                "Predicted_Safety": decision.Safety,
                "Predicted_Urgency": decision.Urgency,
                "Predicted_PrimaryTrade": decision.PrimaryTrade,
                "Predicted_SecondaryTrades": "|".join(
                    decision.SecondaryTrades
                ),
                "Predicted_Outcome": decision.Outcome,
                "Reason": decision.Reason,
            }
        )

        print(
            f"{decision.Case_ID}: "
            f"{decision.Safety} | "
            f"{decision.Urgency} | "
            f"{decision.PrimaryTrade} | "
            f"{decision.SecondaryTrades} | "
            f"{decision.Outcome}"
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
                "Predicted_Outcome",
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