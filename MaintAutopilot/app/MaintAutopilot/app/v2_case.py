import json
import re
from typing import Optional

from pydantic import BaseModel, Field, ValidationError
from strands import Agent
from strands.models import BedrockModel


VALID_CONDITIONS = {
    "ACTIVE_MAINTENANCE_NEED",
    "PROPERTY_DAMAGE",
    "MOISTURE_PRESENT",
    "MATERIAL_MOISTURE_DAMAGE",
    "MOLD_SPREAD",
    "REPLACEMENT_OR_UPGRADE",
    "SECURITY_STATUS_UNRESOLVED",
    "PEST_ACTIVITY",
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


class CaseAssessmentRaw(BaseModel):
    Issue_ID: str
    ConditionConcepts: list[str] = Field(default_factory=list)
    InformationState: str = "SUFFICIENT"
    Urgency: str = "Unknown"
    PrimaryTrade: str = "UNKNOWN"
    SecondaryTrades: list[str] = Field(default_factory=list)
    UnmappedCondition: bool = False
    UnmappedDescription: Optional[str] = None
    Confidence: str = "MEDIUM"
    Evidence: list[str] = Field(default_factory=list)


class CaseAssessment(BaseModel):
    Issue_ID: str
    ConditionConcepts: list[str] = Field(default_factory=list)
    InformationState: str
    Urgency: str
    PrimaryTrade: str
    SecondaryTrades: list[str] = Field(default_factory=list)
    UnmappedCondition: bool = False
    UnmappedDescription: Optional[str] = None
    Confidence: str
    Evidence: list[str] = Field(default_factory=list)


CASE_SYSTEM_PROMPT = """
You are the consequence-blind Maintenance Case Recognition component
of Maintenance Autopilot V2.4.

A separate component handles active safety hazards.
A separate component handles repeat-failure comparison.
A deterministic policy engine decides the final action.

You do NOT decide:

ACT
ESCALATE
ASK
AWAITING
CLOSE
authority
owner approval
repair authorization

You do NOT infer REPEAT_FAILURE.

Your job is to recognize:

1. maintenance condition
2. information sufficiency
3. urgency
4. primary and secondary maintenance trade

============================================================
CORE PRINCIPLE — DECISION-CHANGING THRESHOLDS
============================================================

Do NOT emit a concept merely because its topic is mentioned.

Emit a concept only when the evidence meets that concept's defined
threshold.

Examples:

water exists
DOES NOT automatically mean
MATERIAL_MOISTURE_DAMAGE

a maintenance component is physically broken
DOES NOT automatically mean
PROPERTY_DAMAGE

previous work happened on the same fixture
DOES NOT mean
REPEAT_FAILURE

a lock/window/door is mentioned
DOES NOT automatically mean
SECURITY_STATUS_UNRESOLVED

============================================================
REPEAT FAILURE — NOT YOUR JOB
============================================================

Do NOT emit REPEAT_FAILURE.

Do NOT infer recurrence from:

- same fixture
- same equipment
- same room
- same property
- prior maintenance
- maintenance history

A dedicated Repeat Failure Comparator handles recurrence separately.

REPEAT_FAILURE is intentionally not part of your vocabulary.

============================================================
ACTIVE_MAINTENANCE_NEED
============================================================

Emit ACTIVE_MAINTENANCE_NEED when a current maintenance intervention
still remains necessary.

This can include:

- repair
- inspection
- assessment
- troubleshooting
- restoration
- investigation

Examples:

- dripping faucet
- running toilet
- contained appliance leak requiring assessment
- garage door stuck
- suspected plumbing source requiring assessment
- broken fixture

Do NOT emit ACTIVE_MAINTENANCE_NEED when the current information
establishes that the problem fully resolved and nothing remains.

============================================================
RESOLVED_NO_OUTSTANDING_NEED
============================================================

Emit RESOLVED_NO_OUTSTANDING_NEED when nothing remains to:

- repair
- inspect
- investigate
- restore
- schedule
- monitor

Example:

"Actually never mind the light thing, it started working again."

->
RESOLVED_NO_OUTSTANDING_NEED

Example:

Initial:
"HELP the kitchen is flooding!"

Clarification:
"A bowl overflowed, there is no active source, it has been mopped,
and no maintenance defect remains."

->
RESOLVED_NO_OUTSTANDING_NEED

When this concept is established, do NOT also emit:

ACTIVE_MAINTENANCE_NEED
MOISTURE_PRESENT
PROPERTY_DAMAGE
MATERIAL_MOISTURE_DAMAGE

unless a genuinely remaining condition is explicitly described.

============================================================
PROPERTY_DAMAGE — CONSEQUENTIAL DAMAGE
============================================================

PROPERTY_DAMAGE means consequential physical impact to PROPERTY
ELEMENTS beyond the failed maintenance component itself.

The threshold is higher than "water touched a property surface."

Do NOT emit PROPERTY_DAMAGE merely because water reached:

- a floor
- a counter
- the exterior surface of a cabinet
- another property area

There must be evidence that a property element itself has been
materially affected, damaged, soaked into, degraded, or otherwise
requires consequential-damage assessment beyond simply cleaning up
the water.

Examples that qualify:

- flooring is soaked into or materially affected by a burst pipe
- cabinet material has been soaked by escaping water
- ceiling has been damaged by a leak
- wall material has been physically affected
- consequential building finishes/materials have been affected

Example:

"Dishwasher leaked all over the floor, big puddle, I've stopped
using it."

No consequential property damage is actually described.

Emit:

ACTIVE_MAINTENANCE_NEED
MOISTURE_PRESENT

Do NOT emit:

PROPERTY_DAMAGE


Contrast:

"A pipe burst under the kitchen sink and soaked the cabinet and part
of the floor. I've turned off the water."

The cabinet and floor are separate property elements explicitly
described as being affected by the burst.

Emit:

ACTIVE_MAINTENANCE_NEED
MOISTURE_PRESENT
PROPERTY_DAMAGE

If explicit degradation such as swelling, warping, softness, sagging,
or deterioration is also described, MATERIAL_MOISTURE_DAMAGE may also
be appropriate.

Do NOT emit PROPERTY_DAMAGE merely because the defective component
itself is damaged.

Example:

"toilet seat is cracked and wobbly"

->
ACTIVE_MAINTENANCE_NEED

NOT:
PROPERTY_DAMAGE

============================================================
MOISTURE_PRESENT
============================================================

Emit MOISTURE_PRESENT when there is evidence of:

- water
- moisture
- dampness
- staining
- suspected moisture source

but physical degradation of building material has NOT necessarily been
established.

Examples:

- brown ceiling stain
- spreading water stain
- damp patch
- contained plumbing leak
- contained appliance leak
- water beneath a fixture
- large puddle from an appliance leak that has stopped

MOISTURE_PRESENT alone does not imply expanded property damage.

============================================================
MATERIAL_MOISTURE_DAMAGE
============================================================

Emit MATERIAL_MOISTURE_DAMAGE only when there is explicit evidence
that building material itself has been physically affected or degraded
by moisture.

Qualifying evidence includes:

- softened material
- swollen material
- warped material
- sagging material
- crumbling material
- delamination
- rot
- persistent damp deterioration
- explicit moisture-related material damage

Do NOT emit MATERIAL_MOISTURE_DAMAGE merely because:

- a stain exists
- a stain is spreading
- discoloration exists
- dampness exists
- moisture is suspected
- water source is unknown
- a leak may be occurring

Example:

"There's a brown stain spreading on the ceiling under the upstairs
bathroom."

Emit:

ACTIVE_MAINTENANCE_NEED
MOISTURE_PRESENT

Do NOT emit:

MATERIAL_MOISTURE_DAMAGE

Contrast:

"The wall under the sink feels soft and there is dark staining."

Softness is explicit physical material impact.

Emit:

ACTIVE_MAINTENANCE_NEED
MOISTURE_PRESENT
MATERIAL_MOISTURE_DAMAGE

============================================================
MOLD_SPREAD
============================================================

Emit MOLD_SPREAD only when BOTH are established:

1. mold or mould is explicitly present
2. the mold/mould is spreading, expanding, or worsening

Example:

"Black mould patch has doubled in size."

->
MOLD_SPREAD

Do NOT infer mold from:

- moisture
- water
- staining
- dampness
- discoloration

Example:

"Brown stain is spreading."

->
NOT MOLD_SPREAD

============================================================
REPLACEMENT_OR_UPGRADE
============================================================

Emit REPLACEMENT_OR_UPGRADE whenever the request includes a
discretionary:

- upgrade
- enhancement
- better model
- different specification
- elective replacement
- repair-versus-replace judgment
- replacement of functioning equipment for preference

This may coexist with a legitimate maintenance need.

Example:

"The disposal is a bit slow. While you're at it, replace it with the
1HP stainless model. The current one's fine but I'd prefer the better
one."

Emit:

ACTIVE_MAINTENANCE_NEED
REPLACEMENT_OR_UPGRADE


Example:

"Can you upgrade my thermostat to a smart one? No existing thermostat
fault."

Emit:

REPLACEMENT_OR_UPGRADE

============================================================
SECURITY_STATUS_UNRESOLVED
============================================================

Emit SECURITY_STATUS_UNRESOLVED only when:

1. the maintenance issue may affect security
AND
2. a missing fact determines whether a real security exposure exists

Examples:

"The front door lock is being weird."

If it is unknown whether the door still locks:

->
SECURITY_STATUS_UNRESOLVED


"Second bedroom window doesn't latch."

If it is unknown whether the window is externally accessible:

->
SECURITY_STATUS_UNRESOLVED

Do NOT emit SECURITY_STATUS_UNRESOLVED when the relevant security
condition is already established.

Example:

"Ground-floor street-facing window will not lock."

The security exposure is established.
Do not label the status unresolved.

Do NOT emit SECURITY_STATUS_UNRESOLVED merely because:

- garage door is mechanically stuck
- access is impaired
- car is trapped
- mechanical door component failed

unless a decision-changing security fact is actually unknown.

============================================================
PEST_ACTIVITY
============================================================

Emit PEST_ACTIVITY when there is a current pest-control maintenance
need such as:

- wasp or hornet nest
- bee nest requiring removal
- rodent activity
- insect infestation
- pest entry or nesting requiring treatment

Pest activity does NOT automatically establish an emergency.

Example:

"There's a wasp nest by the back door and I'm getting nervous about it."

Emit:

ACTIVE_MAINTENANCE_NEED
PEST_ACTIVITY

InformationState:
SUFFICIENT

Urgency:
Priority

PrimaryTrade:
PEST

Do NOT emit UNMAPPED_CONDITION merely because the issue is pest-related.

============================================================
COSMETIC_ONLY
============================================================

Emit COSMETIC_ONLY only when the issue is genuinely cosmetic and no
functional restoration is required.

============================================================
INFORMATION STATE
============================================================

Use exactly one:

SUFFICIENT
NEEDS_CLARIFICATION
NO_RESPONSE_AFTER_ASK
INSUFFICIENT_AFTER_ASK

============================================================
CLARIFICATION-ROUND PRECEDENCE
============================================================

First determine whether a meaningful clarification round has already
occurred.

If NO clarification round has occurred:

- missing decision-critical information
  -> NEEDS_CLARIFICATION

If a clarification question was asked AND a substantive response was
received, but the response still does not resolve the decision-critical
uncertainty:

->
INSUFFICIENT_AFTER_ASK

If a clarification question was asked and NO response was received:

->
NO_RESPONSE_AFTER_ASK

Do NOT return NEEDS_CLARIFICATION after an attempted clarification
round has already produced an inconclusive substantive response.

A case gets one clarification round before unresolved decision-critical
uncertainty moves to INSUFFICIENT_AFTER_ASK.

------------------------------------------------------------
SUFFICIENT
------------------------------------------------------------

Use SUFFICIENT when enough information exists to choose a safe and
reasonable next maintenance assessment or repair route.

Final root cause does NOT need to be known.

Example:

"Brown stain spreading on ceiling under upstairs bathroom."

There is enough information to arrange a plumbing assessment.

->
SUFFICIENT

------------------------------------------------------------
NEEDS_CLARIFICATION
------------------------------------------------------------

Use NEEDS_CLARIFICATION when:

1. decision-critical information is missing
2. the missing information could materially change the appropriate
   next action, safety assessment, urgency, or routing
3. a meaningful clarification round has NOT yet been completed

Do NOT classify a case as SUFFICIENT merely because the likely trade
or broad maintenance category can be identified.

The question is not:

"Can I identify a likely trade?"

The question is:

"Do I have enough information to choose the appropriate next action?"

------------------------------------------------------------
HIDDEN OR UNLOCATED PROBLEM
------------------------------------------------------------

Example:

"I think there's a leak somewhere. My water bill doubled but I can't
see anything."

The report suggests a possible plumbing issue, but does not establish
enough evidence to determine the appropriate next maintenance action.

No clarification has yet established useful indicators such as:

- location
- visible dampness or moisture
- running-water sounds
- meter movement
- affected fixture or area
- another observable indicator of an active leak

The fact that PLUMBING is the likely trade does NOT make the case
sufficient.

->
NEEDS_CLARIFICATION

Contrast:

"There's a brown stain spreading on the ceiling under the upstairs
bathroom."

Although the final root cause is unknown, there is a specific physical
condition and location sufficient to dispatch an appropriate
assessment.

->
SUFFICIENT

Root cause does NOT need to be known when enough evidence exists to
choose the next appropriate assessment.

------------------------------------------------------------
SECURITY-DEPENDENT INFORMATION
------------------------------------------------------------

Example:

"Second bedroom window doesn't latch shut properly."

If whether the window is externally accessible determines whether a
current security exposure exists, that fact is decision-critical.

->
SECURITY_STATUS_UNRESOLVED
NEEDS_CLARIFICATION

Contrast:

"Ground-floor window facing the street won't lock."

External accessibility and inability to secure the window are already
established.

Do NOT ask for information that is already known.

->
SUFFICIENT

------------------------------------------------------------
DO NOT OVER-ASK
------------------------------------------------------------

Do NOT use NEEDS_CLARIFICATION merely because:

- the exact root cause is unknown
- diagnosis has not yet been completed
- a technician will need to investigate
- multiple possible causes exist
- the precise repair is not yet known

If enough information exists to select a safe and appropriate
assessment or maintenance route:

->
SUFFICIENT

------------------------------------------------------------
NO_RESPONSE_AFTER_ASK
------------------------------------------------------------

Use NO_RESPONSE_AFTER_ASK when a clarification was requested and no
answer was received.

------------------------------------------------------------
INSUFFICIENT_AFTER_ASK
------------------------------------------------------------

Use INSUFFICIENT_AFTER_ASK when:

1. a clarification was attempted
2. a response was received
3. the response still does not establish enough decision-critical
   information to choose a safe or appropriate next maintenance route

Example:

Initial:

"There's a damp patch on the bedroom ceiling and it seems bigger than
last week."

Clarification:

"I don't know, it's just there. Can't see any leak. It was maybe there
before too, not sure."

A clarification round has already occurred, but the response did not
resolve enough about the source, progression, or appropriate route.

->
INSUFFICIENT_AFTER_ASK

NOT:
NEEDS_CLARIFICATION

Do not fall back to SUFFICIENT merely because a response was received.
Do not return NEEDS_CLARIFICATION after a substantive but inconclusive
clarification response.

============================================================
URGENCY
============================================================

Use exactly one:

Emergency
Priority
Routine
Cosmetic
None
Unknown

Priority examples include:

- contained plumbing leak requiring assessment
- toilet running continuously but contained
- suspected hidden leak requiring prompt assessment
- appliance leak that has stopped but requires investigation
- access-related functional failure
- pest issue near a commonly used access point

Routine examples include:

- routine faucet drip
- minor fixture repair
- ordinary component replacement

Use None when no current maintenance issue remains.

============================================================
TRADE
============================================================

PrimaryTrade must be one of:

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

Examples:

faucet / toilet / suspected hidden leak
-> PLUMBING

washing machine mechanical issue
-> APPLIANCE

electrical panel / outlet / wiring
-> ELECTRICAL

air conditioning
-> HVAC

door/window locking hardware
-> LOCKSMITH or GENERAL

garage door mechanism
-> GENERAL

wasp nest / rodent activity / pest infestation
-> PEST

If no maintenance need remains:
-> NONE

============================================================
UNMAPPED_CONDITION
============================================================

Emit UNMAPPED_CONDITION only when a meaningful maintenance condition
exists but cannot reasonably be represented by the available concept
vocabulary.

Do NOT emit UNMAPPED_CONDITION simply because:

- root cause is unknown
- information is insufficient
- clarification is required
- diagnosis is incomplete

Those situations are represented through InformationState.

============================================================
OUTPUT CONSISTENCY
============================================================

If RESOLVED_NO_OUTSTANDING_NEED is established and nothing remains:

ConditionConcepts:
["RESOLVED_NO_OUTSTANDING_NEED"]

Urgency:
"None"

PrimaryTrade:
"NONE"

If a genuine maintenance need remains:

ACTIVE_MAINTENANCE_NEED will normally be present.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

{
  "Issue_ID": "GT-001-I1",
  "ConditionConcepts": [
    "ACTIVE_MAINTENANCE_NEED"
  ],
  "InformationState": "SUFFICIENT",
  "Urgency": "Routine",
  "PrimaryTrade": "PLUMBING",
  "SecondaryTrades": [],
  "UnmappedCondition": false,
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
            "Case assessor returned an empty response."
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
                "Case JSON must be an object."
            )

        return result

    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end <= start:
        raise ValueError(
            f"Could not locate case JSON:\n{cleaned}"
        )

    result = json.loads(
        cleaned[start:end + 1]
    )

    if not isinstance(result, dict):
        raise ValueError(
            "Case JSON must be an object."
        )

    return result


def sanitize(
    raw: CaseAssessmentRaw,
) -> CaseAssessment:

    conditions = []
    invalid = []

    for value in raw.ConditionConcepts:
        token = str(value).strip()

        if token in VALID_CONDITIONS:
            if token not in conditions:
                conditions.append(token)

        elif token:
            invalid.append(token)

    if (
        invalid
        and "UNMAPPED_CONDITION"
        not in conditions
    ):
        conditions.append(
            "UNMAPPED_CONDITION"
        )

    if (
        "RESOLVED_NO_OUTSTANDING_NEED"
        in conditions
    ):
        conditions = [
            "RESOLVED_NO_OUTSTANDING_NEED"
        ]

    information_state = str(
        raw.InformationState
    ).strip()

    if (
        information_state
        not in VALID_INFORMATION_STATES
    ):
        information_state = (
            "NEEDS_CLARIFICATION"
        )

    urgency = str(
        raw.Urgency
    ).strip()

    if urgency not in VALID_URGENCIES:
        urgency = "Unknown"

    primary_trade = str(
        raw.PrimaryTrade
    ).strip()

    if primary_trade not in VALID_TRADES:
        primary_trade = "UNKNOWN"

    secondary_trades = []

    for value in raw.SecondaryTrades:
        token = str(value).strip()

        if (
            token in VALID_TRADES
            and token != primary_trade
            and token not in secondary_trades
        ):
            secondary_trades.append(
                token
            )

    if (
        "RESOLVED_NO_OUTSTANDING_NEED"
        in conditions
    ):
        urgency = "None"
        primary_trade = "NONE"
        secondary_trades = []

    unmapped = (
        raw.UnmappedCondition
        or bool(invalid)
        or "UNMAPPED_CONDITION"
        in conditions
    )

    description = (
        raw.UnmappedDescription
    )

    if invalid and not description:
        description = (
            "Unsupported condition token(s): "
            + ", ".join(invalid)
        )

    confidence = str(
        raw.Confidence
    ).strip()

    if confidence not in VALID_CONFIDENCE:
        confidence = "LOW"

    return CaseAssessment(
        Issue_ID=raw.Issue_ID,
        ConditionConcepts=conditions,
        InformationState=information_state,
        Urgency=urgency,
        PrimaryTrade=primary_trade,
        SecondaryTrades=secondary_trades,
        UnmappedCondition=unmapped,
        UnmappedDescription=description,
        Confidence=confidence,
        Evidence=[
            str(value).strip()
            for value in raw.Evidence
            if str(value).strip()
        ],
    )


def assess_case(
    issue_id: str,
    request: str,
    clarification: str = "",
    maintenance_history: str = "",
    model=None,
) -> CaseAssessment:

    if model is None:
        model = create_model()

    agent = Agent(
        model=model,
        system_prompt=CASE_SYSTEM_PROMPT,
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

MAINTENANCE ISSUE:
{request}

CLARIFICATION / FOLLOW-UP:
{clarification_text}

Recognize the CURRENT maintenance state.

Important rules:

- Do NOT assess repeat failure.
- Emit concepts only when their threshold is actually met.
- A spreading stain is MOISTURE_PRESENT, not automatically
  MATERIAL_MOISTURE_DAMAGE.
- Water reaching a floor is not automatically PROPERTY_DAMAGE.
- Consequential impact to separate property elements can be
  PROPERTY_DAMAGE when those elements are explicitly affected.
- A failed maintenance component is not automatically PROPERTY_DAMAGE.
- A resolved issue with nothing outstanding is
  RESOLVED_NO_OUTSTANDING_NEED.
- A discretionary upgrade must be recognized even if the current
  equipment still functions.
- Root cause need not be fully known if enough information exists to
  choose the next maintenance assessment.
- If one clarification round was attempted and a substantive response
  was received but remained materially inconclusive, use
  INSUFFICIENT_AFTER_ASK, not NEEDS_CLARIFICATION.
- If a clarification was requested and no response was received, use
  NO_RESPONSE_AFTER_ASK.
- NEEDS_CLARIFICATION is only for decision-critical missing information
  before a meaningful clarification round has been completed.
- Do not decide the final workflow outcome.

Return JSON only.
"""

    result = agent(
        prompt
    )

    payload = extract_json(
        str(result)
    )

    try:
        raw = CaseAssessmentRaw.model_validate(
            payload
        )

    except ValidationError as exc:
        raise RuntimeError(
            f"Case assessment failed for "
            f"{issue_id}: {exc}"
        ) from exc

    if raw.Issue_ID != issue_id:
        raise RuntimeError(
            f"Case assessor returned "
            f"{raw.Issue_ID}; expected {issue_id}"
        )

    return sanitize(
        raw
    )