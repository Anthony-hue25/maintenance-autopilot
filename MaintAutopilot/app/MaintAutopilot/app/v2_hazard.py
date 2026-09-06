import json
import re
from typing import Optional

from pydantic import BaseModel, Field, ValidationError
from strands import Agent
from strands.models import BedrockModel


VALID_HAZARDS = {
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

VALID_CONFIDENCE = {
    "HIGH",
    "MEDIUM",
    "LOW",
}


class HazardAssessmentRaw(BaseModel):
    Issue_ID: str
    HazardConcepts: list[str] = Field(default_factory=list)
    UnmappedHazard: bool = False
    UnmappedDescription: Optional[str] = None
    Confidence: str = "MEDIUM"
    Evidence: list[str] = Field(default_factory=list)


class HazardAssessment(BaseModel):
    Issue_ID: str
    HazardConcepts: list[str] = Field(default_factory=list)
    UnmappedHazard: bool = False
    UnmappedDescription: Optional[str] = None
    Confidence: str
    Evidence: list[str] = Field(default_factory=list)


HAZARD_SYSTEM_PROMPT = """
You are the consequence-blind Hazard Recognition component of
Maintenance Autopilot V2.4.

Your ONE job is to determine what active safety or security hazards
are present in the COMPLETE CURRENT maintenance incident.

You do NOT decide:

ACT
ESCALATE
ASK
AWAITING
CLOSE
authority
repair approval
owner notification
maintenance policy

You recognize what is happening.
A separate deterministic policy engine decides what must follow.

============================================================
CORE PRINCIPLE — ASSESS THE CURRENT STATE
============================================================

Use BOTH:

1. the original request
2. any clarification or follow-up

Clarification may change the meaning of the original report.

If clarification establishes that an alarming condition has stopped,
been contained, was a false alarm, or was misunderstood, assess the
CURRENT condition rather than mechanically repeating the original
wording.

Example:

Original:
"HELP the kitchen is flooding!!"

Clarification:
"A bowl overflowed; no active source remains and it has been mopped."

Current hazard:
NO_ACTIVE_HAZARD

============================================================
CROSS-SYMPTOM SAFETY
============================================================

Assess the COMPLETE report before issue decomposition.

Hazards may emerge from the COMBINATION of symptoms even when each
individual symptom would not independently be critical.

Examples:

water leak
+
breaker tripped when the leak occurred

->
WATER_ELECTRICAL_CONTACT
ELECTRICAL_HAZARD


water spreading
+
electrical outlet immediately in its path

->
WATER_ELECTRICAL_CONTACT


gas indication
+
possible ignition source

->
GAS_HAZARD

Do not weaken a cross-symptom hazard merely because downstream
maintenance issues can be decomposed.

============================================================
GAS_HAZARD
============================================================

Emit GAS_HAZARD when the report semantically indicates a credible
current combustible-gas leak, release, unsafe gas connection, or
similar gas safety condition.

Recognize MEANING rather than exact vocabulary.

Examples that may indicate GAS_HAZARD:

- smell of gas
- rotten-egg odor near gas equipment
- sulphur-like odor near a range
- suspected gas escaping
- damaged gas connection with evidence of release

Do NOT require the exact phrase "gas smell."

Do not emit GAS_HAZARD for a gas appliance maintenance problem when
there is no indication of gas release or another gas safety condition.

============================================================
CO_HAZARD
============================================================

Emit CO_HAZARD when there is credible evidence of a current
carbon-monoxide condition or exposure.

Do not infer carbon monoxide merely because combustion equipment
exists.

============================================================
ACTIVE_FIRE_OR_SMOKE
============================================================

Emit ACTIVE_FIRE_OR_SMOKE when there is explicit current evidence of:

- smoke
- fire
- active burning
- combustion

This includes smoke coming from:

- electrical panels
- electrical equipment
- wiring
- outlets
- appliances
- HVAC equipment
- building systems

Example:

"There's smoke coming from the electrical panel."

->
ACTIVE_FIRE_OR_SMOKE
ELECTRICAL_HAZARD

Explicit current smoke must not be downgraded merely because the exact
ignition source is unknown.

============================================================
ELECTRICAL_HAZARD
============================================================

Emit ELECTRICAL_HAZARD for a credible current dangerous electrical
condition including:

- sparking
- burning electrical equipment
- smoke from electrical equipment
- exposed live wiring
- dangerous electrical contact
- electrical overheating/fire condition
- water interacting with electrical equipment
- a breaker or protective device tripping in connection with a water
  leak or other credible electrical fault

Example:

"Smoke is coming from the electrical panel."

->
ELECTRICAL_HAZARD
ACTIVE_FIRE_OR_SMOKE


Example:

"The washing machine leaked and the breaker tripped when it happened."

->
ELECTRICAL_HAZARD
WATER_ELECTRICAL_CONTACT

A breaker having tripped does NOT prove the situation is safe.

============================================================
WATER_ELECTRICAL_CONTACT
============================================================

Emit WATER_ELECTRICAL_CONTACT when water is:

- contacting electrical equipment
- contacting an outlet/socket/wiring
- immediately adjacent to energized electrical equipment
- moving toward electrical equipment
- credibly threatening electrical equipment
- associated with an electrical protective-device trip

The water does not need to have physically reached the electrical
source yet if it is actively advancing toward it.

Examples:

"Water is spreading toward the socket."

->
WATER_ELECTRICAL_CONTACT


"Leak from washing machine and breaker tripped."

->
WATER_ELECTRICAL_CONTACT


"Water under sink; no outlets nearby."

->
NOT WATER_ELECTRICAL_CONTACT


"AC is dripping, but there is no electrical equipment near the water."

->
NOT WATER_ELECTRICAL_CONTACT

============================================================
UNCONTROLLED_WATER
============================================================

Emit UNCONTROLLED_WATER only when BOTH are true:

1. Water has escaped, or is actively escaping, its intended containment.
2. The substantial uncontrolled escape is CURRENTLY continuing.

Examples that qualify:

- pipe actively pouring water onto the floor and cannot be stopped
- ceiling actively pouring water into a room
- fixture continuously overflowing onto the property
- substantial active flooding
- major ongoing water ingress

Do NOT emit UNCONTROLLED_WATER for:

- a stain
- dampness
- evidence of historical moisture
- a puddle from an event that has stopped
- dishwasher/appliance leak that stopped when use stopped
- water remaining within normal plumbing containment
- toilet continuously running into its own bowl or tank
- faucet flow remaining inside a sink
- a contained leak
- suspected hidden moisture with no visible active flow
- a leak that occurs only while equipment is operated and stops when
  operation stops

Critical distinction:

CURRENT substantial water escaping containment
-> may be UNCONTROLLED_WATER

Evidence that water leaked previously, or may be leaking somewhere
without visible ongoing escape
-> NOT UNCONTROLLED_WATER

============================================================
CURRENT-STATE PRECEDENCE FOR WATER
============================================================

If the report explicitly establishes that the water-producing activity
has stopped and no ongoing flow remains, do NOT emit
UNCONTROLLED_WATER unless substantial uncontrolled water is still
continuing independently.

Example:

"dishwasher leaked all over the floor, big puddle, I've stopped using it"

The appliance is no longer operating and no continuing water flow is
reported.

->
NOT UNCONTROLLED_WATER

A large prior puddle does not make the CURRENT state an uncontrolled
water emergency.

============================================================
SEWAGE_HAZARD
============================================================

Emit SEWAGE_HAZARD for credible:

- sewage release
- sewage backup
- direct sewage contamination
- wastewater contamination creating a health exposure

Odor alone is insufficient unless the report provides evidence that
the source is actually sewage or wastewater contamination.

============================================================
STRUCTURAL_FALL_RISK
============================================================

Emit STRUCTURAL_FALL_RISK when there is a credible current:

- fall hazard
- collapse risk
- failed support
- unstable safety-critical structural component
- loose/wobbly handrail creating a fall exposure
- unsafe stair/balcony/guard condition

Distinguish structural safety from cosmetic or minor building defects.

============================================================
SECURITY_EXPOSURE
============================================================

Emit SECURITY_EXPOSURE only when a current security exposure is
ESTABLISHED.

Examples:

"Ground-floor street-facing window will not lock."

->
SECURITY_EXPOSURE


"Externally accessible door cannot be secured."

->
SECURITY_EXPOSURE

Do NOT emit SECURITY_EXPOSURE merely because:

- a lock is behaving strangely
- a window does not latch but external accessibility is unknown
- a garage door is mechanically stuck
- access is inconvenient

Example:

"The front door lock is being weird."

If it is unknown whether the door can still be secured:

->
NOT yet SECURITY_EXPOSURE

That is an information question for the case assessor.

============================================================
NO_ACTIVE_HAZARD
============================================================

Emit NO_ACTIVE_HAZARD when no active safety or security hazard is
established.

Examples:

- routine faucet drip
- toilet running inside normal containment
- contained appliance leak with no electrical exposure
- minor component defect
- routine plumbing issue
- resolved spill with no remaining hazard
- maintenance issue requiring priority attention but not a safety
  escalation

Safety and urgency are NOT the same thing.

A Priority maintenance issue may still have:

NO_ACTIVE_HAZARD

============================================================
UNMAPPED_HAZARD
============================================================

Emit UNMAPPED_HAZARD only when:

1. there appears to be a credible active safety concern
AND
2. that concern cannot be represented by the available hazard
   vocabulary

Do NOT use UNMAPPED_HAZARD merely because:

- maintenance diagnosis is unclear
- root cause is unknown
- trade is uncertain
- clarification is needed for a non-safety question

Those belong to the case-assessment layer.

============================================================
CONSISTENCY RULES
============================================================

If any real hazard concept is emitted, do NOT also emit
NO_ACTIVE_HAZARD.

If no hazard is established, emit:

["NO_ACTIVE_HAZARD"]

Do not invent hazards merely because the report contains words
associated with water, electricity, damage, security, or gas.

Evaluate whether the hazard THRESHOLD is actually met.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

No markdown.
No code fences.
No explanation outside JSON.

Use this shape:

{
  "Issue_ID": "GT-001-FULL",
  "HazardConcepts": ["NO_ACTIVE_HAZARD"],
  "UnmappedHazard": false,
  "UnmappedDescription": null,
  "Confidence": "HIGH",
  "Evidence": [
    "short factual evidence from the report"
  ]
}
"""


def create_model():
    return BedrockModel(
        model_id="us.amazon.nova-2-lite-v1:0",
        region_name="us-east-1",
        temperature=0,
    )


def extract_json(text: str) -> dict:
    cleaned = str(text).strip()

    if not cleaned:
        raise ValueError(
            "Hazard assessor returned an empty response."
        )

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
        result = json.loads(cleaned)

        if not isinstance(result, dict):
            raise ValueError(
                "Hazard JSON must be an object."
            )

        return result

    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end <= start:
        raise ValueError(
            f"Could not locate hazard JSON:\n{cleaned}"
        )

    candidate = cleaned[
        start:end + 1
    ]

    try:
        result = json.loads(candidate)

    except json.JSONDecodeError as exc:
        raise ValueError(
            "Invalid hazard JSON.\n"
            f"Raw response:\n{cleaned}"
        ) from exc

    if not isinstance(result, dict):
        raise ValueError(
            "Hazard JSON must be an object."
        )

    return result


def sanitize(
    raw: HazardAssessmentRaw,
) -> HazardAssessment:

    hazards = []
    invalid = []

    for value in raw.HazardConcepts:
        token = str(value).strip()

        if token in VALID_HAZARDS:
            if token not in hazards:
                hazards.append(token)

        elif token:
            invalid.append(token)

    unmapped = (
        raw.UnmappedHazard
        or bool(invalid)
        or "UNMAPPED_HAZARD" in hazards
    )

    if (
        invalid
        and "UNMAPPED_HAZARD" not in hazards
    ):
        hazards.append(
            "UNMAPPED_HAZARD"
        )

    if not hazards:
        hazards = [
            "UNMAPPED_HAZARD"
        ]
        unmapped = True

    if (
        "NO_ACTIVE_HAZARD" in hazards
        and len(hazards) > 1
    ):
        hazards = [
            value
            for value in hazards
            if value != "NO_ACTIVE_HAZARD"
        ]

    confidence = str(
        raw.Confidence
    ).strip()

    if confidence not in VALID_CONFIDENCE:
        confidence = "LOW"

    description = (
        raw.UnmappedDescription
    )

    if invalid and not description:
        description = (
            "Unsupported hazard token(s): "
            + ", ".join(invalid)
        )

    return HazardAssessment(
        Issue_ID=raw.Issue_ID,
        HazardConcepts=hazards,
        UnmappedHazard=unmapped,
        UnmappedDescription=description,
        Confidence=confidence,
        Evidence=[
            str(value).strip()
            for value in raw.Evidence
            if str(value).strip()
        ],
    )


def assess_hazards(
    issue_id: str,
    request: str,
    clarification: str = "",
    model=None,
) -> HazardAssessment:

    if model is None:
        model = create_model()

    agent = Agent(
        model=model,
        system_prompt=HAZARD_SYSTEM_PROMPT,
        callback_handler=None,
    )

    clarification_text = (
        clarification.strip()
        if clarification.strip()
        else "None provided"
    )

    prompt = f"""
Issue_ID:
{issue_id}

COMPLETE ORIGINAL REPORT:
{request}

CLARIFICATION / FOLLOW-UP:
{clarification_text}

Assess the CURRENT hazard meaning across the COMPLETE incident.

Remember:

- Consider cross-symptom hazards before decomposition.
- Explicit smoke from electrical equipment is a fire/smoke AND
  electrical hazard.
- Continuous plumbing flow inside normal containment is NOT
  uncontrolled water.
- A stopped prior leak is not a current uncontrolled-water hazard.
- Current clarification may override alarming original wording.
- Recognize hazards semantically, not by keyword matching.
- Do not decide the maintenance outcome.

Return JSON only.
"""

    result = agent(
        prompt
    )

    payload = extract_json(
        str(result)
    )

    try:
        raw = HazardAssessmentRaw.model_validate(
            payload
        )

    except ValidationError as exc:
        raise RuntimeError(
            f"Hazard assessment failed for "
            f"{issue_id}: {exc}"
        ) from exc

    if raw.Issue_ID != issue_id:
        raise RuntimeError(
            f"Hazard assessor returned "
            f"{raw.Issue_ID}; expected {issue_id}"
        )

    return sanitize(
        raw
    )