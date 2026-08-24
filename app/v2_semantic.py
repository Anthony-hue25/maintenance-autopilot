import json
import re
from typing import Optional

from pydantic import BaseModel, Field, ValidationError
from strands import Agent
from strands.models import BedrockModel


# ============================================================
# FROZEN V2 SEMANTIC VOCABULARY
# ============================================================

VALID_HAZARD_CONCEPTS = {
    "GAS_HAZARD",
    "CO_HAZARD",
    "ACTIVE_FIRE_OR_SMOKE",
    "ELECTRICAL_HAZARD",
    "WATER_ELECTRICAL_CONTACT",
    "UNCONTROLLED_WATER",
    "SEWAGE_HAZARD",
    "STRUCTURAL_FALL_RISK",
    "SECURITY_EXPOSURE",
    "NO_ACTIVE_HAZARD",
    "UNMAPPED_HAZARD",
}


VALID_CONDITION_CONCEPTS = {
    "ACTIVE_MAINTENANCE_NEED",
    "PROPERTY_DAMAGE",
    "MOISTURE_DAMAGE",
    "MOLD_SPREAD",
    "REPLACEMENT_OR_UPGRADE",
    "REPEAT_FAILURE",
    "COSMETIC_ONLY",
    "RESOLVED_NO_OUTSTANDING_NEED",
    "UNMAPPED_CONDITION",
}


VALID_INFORMATION_STATES = {
    "SUFFICIENT",
    "NEEDS_CLARIFICATION",
    "NO_RESPONSE_AFTER_ASK",
    "INSUFFICIENT_AFTER_ASK",
}


VALID_URGENCIES = {
    "Emergency",
    "Priority",
    "Routine",
    "Cosmetic",
    "None",
    "Unknown",
}


VALID_TRADES = {
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
}


VALID_CONFIDENCE = {
    "HIGH",
    "MEDIUM",
    "LOW",
}


# ============================================================
# RAW JSON MODEL
# ============================================================

class SemanticAssessmentRaw(BaseModel):
    Case_ID: str

    HazardConcepts: list[str] = Field(default_factory=list)
    ConditionConcepts: list[str] = Field(default_factory=list)

    InformationState: str = "SUFFICIENT"
    Urgency: str = "Unknown"

    PrimaryTrade: str = "UNKNOWN"
    SecondaryTrades: list[str] = Field(default_factory=list)

    QuotedCost: Optional[float] = None

    RepeatFailureDetected: bool = False
    ReplacementOrUpgrade: bool = False
    ResolvedNoOutstandingNeed: bool = False

    UnmappedConcern: bool = False
    UnmappedDescription: Optional[str] = None

    Confidence: str = "MEDIUM"

    Evidence: list[str] = Field(default_factory=list)


# ============================================================
# CLEAN SEMANTIC OBJECT
# ============================================================

class SemanticAssessment(BaseModel):
    Case_ID: str

    HazardConcepts: list[str] = Field(default_factory=list)
    ConditionConcepts: list[str] = Field(default_factory=list)

    InformationState: str
    Urgency: str

    PrimaryTrade: str
    SecondaryTrades: list[str] = Field(default_factory=list)

    QuotedCost: Optional[float] = None

    RepeatFailureDetected: bool = False
    ReplacementOrUpgrade: bool = False
    ResolvedNoOutstandingNeed: bool = False

    UnmappedConcern: bool = False
    UnmappedDescription: Optional[str] = None

    Confidence: str = "MEDIUM"

    Evidence: list[str] = Field(default_factory=list)


# ============================================================
# CONSEQUENCE-BLIND SEMANTIC PROMPT
# ============================================================

SEMANTIC_SYSTEM_PROMPT = """
You are the Semantic Assessment component of Maintenance Autopilot V2.

Your ONLY job is to determine WHAT IS HAPPENING.

You MUST NOT decide or recommend:
ACT
ESCALATE
ASK
AWAITING
CLOSE
owner approval
repair authorization

You do not know downstream policy.

Recognize meaning rather than matching exact words.

============================================================
IMPORTANT: ACTIVE HAZARD VS MAINTENANCE CONDITION
============================================================

A hazard concept means the hazard is CURRENTLY credible and active.

Do NOT label something hazardous merely because:
- water exists somewhere,
- an appliance uses electricity,
- a plumbing fixture is leaking,
- a sewage-like smell is reported,
- a problem happened earlier but has now stopped,
- property damage might eventually occur.

Use NO_ACTIVE_HAZARD when maintenance is needed but no current
safety/security hazard is established.

Clarification/follow-up information may RESOLVE or OVERRIDE the
initial wording.

Example:
Initial report says "flooding", but follow-up confirms a bowl
overflowed, there is no active source, and it has been mopped.
That is NOT UNCONTROLLED_WATER now.

============================================================
HAZARD CONCEPTS
============================================================

GAS_HAZARD
Credible current combustible-gas release, escaped gas, unsafe gas
connection/supply, or equivalent condition.

Recognize indirect descriptions of gas leakage by meaning, not only
the literal word "gas".

CO_HAZARD
Credible current carbon-monoxide condition.

ACTIVE_FIRE_OR_SMOKE
Actual smoke, fire, combustion, or credible active burning.

A smoke detector merely chirping for battery/service does NOT count.

ELECTRICAL_HAZARD
A CURRENT dangerous electrical condition:
sparking, burning electrical equipment, exposed live wiring, dangerous
electrical contact, or similarly unsafe fault.

Do NOT use ELECTRICAL_HAZARD merely because:
- an electrical appliance is broken,
- a breaker tripped and no active danger remains,
- a disposal/dishwasher/AC uses electricity.

WATER_ELECTRICAL_CONTACT
Water is CURRENTLY in credible contact with, immediately adjacent to,
or threatening an electrical outlet, socket, live wiring, or energized
equipment.

Do NOT infer this simply because an electrical appliance and water are
mentioned in the same report.

UNCONTROLLED_WATER
Water is CURRENTLY escaping containment substantially, actively flowing,
pouring, flooding, or entering the property in a manner requiring
immediate mitigation.

A small contained leak, puddle, drip, stopped leak, or already-resolved
overflow does NOT qualify.

SEWAGE_HAZARD
Actual sewage release, sewage backup, or direct sanitary contamination.

A sewage ODOR alone does not establish sewage release.

STRUCTURAL_FALL_RISK
A CURRENT credible physical danger from a structural/support element,
such as unstable railing, dangerous walking surface, collapse risk,
falling material, unsafe balcony/stair/support, etc.

Do not use this merely because property material is damp or stained.

SECURITY_EXPOSURE
The property currently cannot be secured, or there is a credible current
security exposure.

NO_ACTIVE_HAZARD
No current safety/security hazard is established.

UNMAPPED_HAZARD
A credible current safety issue exists but none of the hazard concepts
fits it.

============================================================
CONDITION CONCEPTS
============================================================

ACTIVE_MAINTENANCE_NEED
An unresolved maintenance need remains.

PROPERTY_DAMAGE
Actual physical property damage has occurred, for example swelling,
warping, damaged finishes/materials, or other consequential damage.

MOISTURE_DAMAGE
Building materials are credibly being degraded or damaged by moisture.

Do NOT use merely for:
- a small puddle,
- an ordinary appliance leak,
- condensate needing repair,
unless material/building damage is described.

MOLD_SPREAD
Mold/mould is materially expanding, spreading, or worsening.

REPLACEMENT_OR_UPGRADE
A replacement, upgrade, enhancement, or repair-versus-replace decision
exists.

REPEAT_FAILURE
The SAME or MATERIALLY RELATED failure mode has recurred.

Very important:
- same fixture does NOT automatically mean repeat failure
- prior faucet work does not make a new faucet drip a repeat unless it
  is materially the same failure
- prior toilet clog + current running-fill fault are different failures
- ceiling stain history does not automatically make a new plumbing
  symptom a repeat failure

Use maintenance history narrowly.

COSMETIC_ONLY
Issue is cosmetic rather than functional.

RESOLVED_NO_OUTSTANDING_NEED
The reported issue has resolved and nothing remains to repair,
investigate, schedule, or monitor.

UNMAPPED_CONDITION
A meaningful maintenance condition exists but cannot be represented
with the defined vocabulary.

============================================================
INFORMATION STATE
============================================================

Use exactly one:

SUFFICIENT
NEEDS_CLARIFICATION
NO_RESPONSE_AFTER_ASK
INSUFFICIENT_AFTER_ASK

SUFFICIENT
Enough is known to identify the maintenance condition and reasonable
routing. Root cause does not need to be known.

NEEDS_CLARIFICATION
No clarification round has yet resolved a missing fact that materially
changes recognition or routing.

NO_RESPONSE_AFTER_ASK
A clarification was actually requested and the tenant provided no
response.

Do NOT use NEEDS_CLARIFICATION when the case explicitly says a
clarification was asked and no response was received.

INSUFFICIENT_AFTER_ASK
Tenant responded to the permitted clarification round, but the answer
remained decision-relevantly unclear.

============================================================
URGENCY
============================================================

Emergency
Priority
Routine
Cosmetic
None
Unknown

Emergency only when facts indicate immediate safety/protective need.

Priority for meaningful functional loss or prompt damage prevention
without an active emergency.

Routine for normal maintenance that can be scheduled.

============================================================
TRADE
============================================================

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

============================================================
CONFIDENCE
============================================================

HIGH
MEDIUM
LOW

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.
No markdown fences.
No explanation outside JSON.

Exact shape:

{
  "Case_ID": "CASE-ID",
  "HazardConcepts": ["NO_ACTIVE_HAZARD"],
  "ConditionConcepts": ["ACTIVE_MAINTENANCE_NEED"],
  "InformationState": "SUFFICIENT",
  "Urgency": "Routine",
  "PrimaryTrade": "PLUMBING",
  "SecondaryTrades": [],
  "QuotedCost": null,
  "RepeatFailureDetected": false,
  "ReplacementOrUpgrade": false,
  "ResolvedNoOutstandingNeed": false,
  "UnmappedConcern": false,
  "UnmappedDescription": null,
  "Confidence": "HIGH",
  "Evidence": ["short factual evidence"]
}

If no active hazard exists, include NO_ACTIVE_HAZARD.

Do not combine NO_ACTIVE_HAZARD with another hazard concept.

Evidence must contain factual observations only, never downstream policy.
"""


# ============================================================
# MODEL
# ============================================================

def create_semantic_model():
    return BedrockModel(
        model_id="us.amazon.nova-2-lite-v1:0",
        region_name="us-east-1",
        temperature=0,
    )


# ============================================================
# JSON PARSING
# ============================================================

def extract_json_object(text: str) -> dict:
    if text is None:
        raise ValueError("Semantic model returned no text.")

    cleaned = str(text).strip()

    if not cleaned:
        raise ValueError("Semantic model returned an empty response.")

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    )

    try:
        parsed = json.loads(cleaned)

        if not isinstance(parsed, dict):
            raise ValueError("Semantic JSON must be an object.")

        return parsed

    except json.JSONDecodeError:
        pass

    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")

    if (
        first_brace == -1
        or last_brace == -1
        or last_brace <= first_brace
    ):
        raise ValueError(
            "Could not locate JSON object.\n"
            f"Raw response:\n{cleaned}"
        )

    candidate = cleaned[first_brace:last_brace + 1]

    try:
        parsed = json.loads(candidate)

    except json.JSONDecodeError as exc:
        raise ValueError(
            "Invalid semantic JSON.\n"
            f"Raw response:\n{cleaned}"
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError("Semantic JSON must be an object.")

    return parsed


# ============================================================
# SANITIZATION
# ============================================================

def _clean_token(value) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _sanitize_list(
    values,
    valid_values,
    unmapped_token=None,
):
    clean = []
    invalid = []

    for value in values or []:
        token = _clean_token(value)

        if token in valid_values:
            if token not in clean:
                clean.append(token)
        elif token:
            invalid.append(token)

    if invalid and unmapped_token:
        if unmapped_token not in clean:
            clean.append(unmapped_token)

    return clean, invalid


def sanitize_assessment(
    raw: SemanticAssessmentRaw,
) -> SemanticAssessment:

    hazards, invalid_hazards = _sanitize_list(
        raw.HazardConcepts,
        VALID_HAZARD_CONCEPTS,
        "UNMAPPED_HAZARD",
    )

    conditions, invalid_conditions = _sanitize_list(
        raw.ConditionConcepts,
        VALID_CONDITION_CONCEPTS,
        "UNMAPPED_CONDITION",
    )

    secondary_trades, invalid_secondary = _sanitize_list(
        raw.SecondaryTrades,
        VALID_TRADES,
    )

    information_state = _clean_token(raw.InformationState)

    if information_state not in VALID_INFORMATION_STATES:
        information_state = "NEEDS_CLARIFICATION"

    urgency = _clean_token(raw.Urgency)

    if urgency not in VALID_URGENCIES:
        urgency = "Unknown"

    primary_trade = _clean_token(raw.PrimaryTrade)

    if primary_trade not in VALID_TRADES:
        primary_trade = "UNKNOWN"

    confidence = _clean_token(raw.Confidence)

    if confidence not in VALID_CONFIDENCE:
        confidence = "LOW"

    invalid_items = (
        invalid_hazards
        + invalid_conditions
        + invalid_secondary
    )

    unmapped = (
        raw.UnmappedConcern
        or bool(invalid_items)
        or "UNMAPPED_HAZARD" in hazards
        or "UNMAPPED_CONDITION" in conditions
    )

    if raw.UnmappedDescription:
        unmapped_description = raw.UnmappedDescription
    elif invalid_items:
        unmapped_description = (
            "Unsupported semantic token(s): "
            + ", ".join(invalid_items)
        )
    else:
        unmapped_description = None

    # Active hazard always wins over contradictory NO_ACTIVE_HAZARD.
    if (
        "NO_ACTIVE_HAZARD" in hazards
        and len(hazards) > 1
    ):
        hazards = [
            h
            for h in hazards
            if h != "NO_ACTIVE_HAZARD"
        ]

    # No hazard token returned = fail-safe unmapped.
    if not hazards:
        hazards = ["UNMAPPED_HAZARD"]
        unmapped = True

        if not unmapped_description:
            unmapped_description = (
                "Semantic assessor returned no hazard concept."
            )

    return SemanticAssessment(
        Case_ID=raw.Case_ID,
        HazardConcepts=hazards,
        ConditionConcepts=conditions,
        InformationState=information_state,
        Urgency=urgency,
        PrimaryTrade=primary_trade,
        SecondaryTrades=secondary_trades,
        QuotedCost=raw.QuotedCost,
        RepeatFailureDetected=raw.RepeatFailureDetected,
        ReplacementOrUpgrade=raw.ReplacementOrUpgrade,
        ResolvedNoOutstandingNeed=raw.ResolvedNoOutstandingNeed,
        UnmappedConcern=unmapped,
        UnmappedDescription=unmapped_description,
        Confidence=confidence,
        Evidence=[
            str(item).strip()
            for item in raw.Evidence
            if str(item).strip()
        ],
    )


# ============================================================
# SEMANTIC CALL
# ============================================================

def assess_semantics(
    case_id: str,
    unit: str,
    request: str,
    clarification: str = "",
    maintenance_history: str = "",
    model=None,
) -> SemanticAssessment:

    if model is None:
        model = create_semantic_model()

    agent = Agent(
        model=model,
        system_prompt=SEMANTIC_SYSTEM_PROMPT,
        callback_handler=None,
    )

    clarification_text = (
        clarification.strip()
        if clarification.strip()
        else "None provided"
    )

    history_text = (
        maintenance_history.strip()
        if maintenance_history.strip()
        else "No relevant maintenance history provided"
    )

    prompt = f"""
Perform a consequence-blind semantic assessment.

Case_ID:
{case_id}

Unit:
{unit}

Tenant Request:
{request}

Clarification / Follow-up:
{clarification_text}

Relevant Maintenance History:
{history_text}

Important:
Interpret the CURRENT state using both the original request and any
follow-up. Later clarification may resolve or supersede alarming
initial wording.

Return ONLY the requested JSON object.
"""

    try:
        result = agent(prompt)

    except Exception as exc:
        raise RuntimeError(
            f"Semantic LLM call failed for {case_id}: {exc}"
        ) from exc

    response_text = str(result).strip()

    try:
        payload = extract_json_object(response_text)

    except Exception as exc:
        raise RuntimeError(
            f"Could not parse semantic JSON for {case_id}: {exc}"
        ) from exc

    try:
        raw = SemanticAssessmentRaw.model_validate(payload)

    except ValidationError as exc:
        raise RuntimeError(
            f"Semantic JSON failed schema validation for "
            f"{case_id}.\n"
            f"Payload:\n{json.dumps(payload, indent=2)}\n"
            f"Error:\n{exc}"
        ) from exc

    if raw.Case_ID != case_id:
        raise RuntimeError(
            f"Semantic assessor returned {raw.Case_ID}; "
            f"expected {case_id}"
        )

    return sanitize_assessment(raw)