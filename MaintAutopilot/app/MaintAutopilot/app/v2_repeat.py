import json
import re
from typing import Literal

from pydantic import BaseModel, ValidationError
from strands import Agent
from strands.models import BedrockModel


class RepeatAssessmentRaw(BaseModel):
    Issue_ID: str
    Result: str
    Confidence: str = "MEDIUM"
    Reason: str = ""


RepeatResult = Literal[
    "SAME_FAILURE_MODE",
    "DIFFERENT_FAILURE_MODE",
    "NO_COMPARABLE_HISTORY",
    "UNCERTAIN",
]


class RepeatAssessment(BaseModel):
    Issue_ID: str
    Result: RepeatResult
    Confidence: str
    Reason: str


REPEAT_SYSTEM_PROMPT = """
You are the Repeat Failure Comparator for Maintenance Autopilot V2.5.

Your ONE job is to determine whether the CURRENT maintenance failure
is the SAME or MATERIALLY RELATED functional failure mode as a
previous failure.

You do NOT decide:

ACT
ESCALATE
ASK
AWAITING
CLOSE
urgency
safety
authority

============================================================
SOURCES OF RECURRENCE EVIDENCE
============================================================

Repeat evidence may come from:

1. the current maintenance request
2. clarification/follow-up information
3. stored maintenance history

Use all three sources together.

Clarification may explicitly contain maintenance-history evidence.

Example:

Current:
"sink's a bit slow again"

Clarification:
"History shows the same drain was cleared five weeks ago."

->
SAME_FAILURE_MODE

============================================================
CORE RULE — AFFIRMATIVE RECURRENCE EVIDENCE
============================================================

SAME_FAILURE_MODE requires affirmative evidence that the same or
materially related functional failure occurred previously.

Same fixture alone is NOT enough.
Same equipment alone is NOT enough.
Same room or property is NOT enough.
Previous unrelated maintenance is NOT enough.
Urgency is NOT recurrence evidence.
Being the only fixture is NOT recurrence evidence.

============================================================
SAME_FAILURE_MODE
============================================================

Use when the current functional symptom matches or materially relates
to an established prior symptom/failure.

Example:

Current:
"sink's a bit slow again"

Clarification/history:
"same drain was cleared five weeks ago"

Slow-drain symptoms have recurred.

->
SAME_FAILURE_MODE


Example:

Current:
"kitchen sink draining slow again, same as a few weeks back"

Prior evidence:
previous slow drain / drain-clear event

->
SAME_FAILURE_MODE


Example:

Current:
"same shower drain is backing up again, third time now"

Prior evidence:
shower drain backed up twice recently

->
SAME_FAILURE_MODE

============================================================
DIFFERENT_FAILURE_MODE
============================================================

Use when the same asset has prior history but the functional failure
is materially different.

Example:

Prior:
toilet clogged

Current:
toilet constantly running / fill fault

->
DIFFERENT_FAILURE_MODE


Example:

Prior:
toilet clogged

Current:
toilet will not stop filling

->
DIFFERENT_FAILURE_MODE

Do not classify recurrence merely because both events involve the
same toilet.

============================================================
NO_COMPARABLE_HISTORY
============================================================

Use when no affirmative evidence establishes the same or materially
related prior failure.

Example:

Current:
toilet will not flush

Clarification:
it is the only toilet in the property

No prior no-flush failure is established.

->
NO_COMPARABLE_HISTORY

The importance or uniqueness of the fixture does NOT make the failure
a recurrence.

============================================================
UNCERTAIN
============================================================

Use only when there may be a relationship but available evidence is
too vague to determine whether the failure modes are materially the
same.

UNCERTAIN does NOT mean SAME_FAILURE_MODE.

============================================================
DECISION TEST
============================================================

Ask:

"Can I point to affirmative evidence in the request, clarification,
or history that this same functional failure occurred before?"

If YES:
-> SAME_FAILURE_MODE

If previous failure is clearly different:
-> DIFFERENT_FAILURE_MODE

If no comparable prior failure is established:
-> NO_COMPARABLE_HISTORY

If evidence is genuinely ambiguous:
-> UNCERTAIN

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

No markdown.
No code fences.
No explanation outside JSON.

Use exactly this shape:

{
  "Issue_ID": "GT-001-I1",
  "Result": "NO_COMPARABLE_HISTORY",
  "Confidence": "HIGH",
  "Reason": "No affirmative evidence of the same failure mode."
}
"""


def create_model():
    return BedrockModel(
        model_id="us.amazon.nova-2-lite-v1:0",
        region_name="us-east-1",
        temperature=0,
    )


def extract_json(text: str) -> dict:
    cleaned = str(
        text
    ).strip()

    if not cleaned:
        raise ValueError(
            "Repeat assessor returned an empty response."
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
        result = json.loads(
            cleaned
        )

        if not isinstance(
            result,
            dict,
        ):
            raise ValueError(
                "Repeat JSON must be an object."
            )

        return result

    except json.JSONDecodeError:
        pass

    start = cleaned.find(
        "{"
    )

    end = cleaned.rfind(
        "}"
    )

    if (
        start == -1
        or end <= start
    ):
        raise ValueError(
            "Could not locate repeat-assessment JSON.\n"
            f"Raw response:\n{cleaned}"
        )

    candidate = cleaned[
        start:end + 1
    ]

    try:
        result = json.loads(
            candidate
        )

    except json.JSONDecodeError as exc:
        raise ValueError(
            "Invalid repeat-assessment JSON.\n"
            f"Raw response:\n{cleaned}"
        ) from exc

    if not isinstance(
        result,
        dict,
    ):
        raise ValueError(
            "Repeat JSON must be an object."
        )

    return result


def assess_repeat(
    issue_id: str,
    request: str,
    clarification: str = "",
    maintenance_history: str = "",
    model=None,
) -> RepeatAssessment:

    if model is None:
        model = create_model()

    agent = Agent(
        model=model,
        system_prompt=REPEAT_SYSTEM_PROMPT,
        callback_handler=None,
    )

    clarification_text = (
        clarification.strip()
        if clarification.strip()
        else "No clarification supplied."
    )

    history_text = (
        maintenance_history.strip()
        if maintenance_history.strip()
        else "No stored maintenance history supplied."
    )

    prompt = f"""
Issue_ID:
{issue_id}

CURRENT MAINTENANCE FAILURE:
{request}

CLARIFICATION / FOLLOW-UP:
{clarification_text}

STORED MAINTENANCE HISTORY:
{history_text}

Determine whether there is affirmative evidence that the SAME or
MATERIALLY RELATED functional failure occurred previously.

Use evidence from the current request, clarification, and stored
history together.

Important:

- Same asset alone does not establish recurrence.
- Importance or urgency does not establish recurrence.
- A clarification statement such as "History shows the same drain was
  cleared five weeks ago" is valid recurrence evidence.
- If no comparable previous failure is established, use
  NO_COMPARABLE_HISTORY.

Return JSON only.
"""

    result = agent(
        prompt
    )

    payload = extract_json(
        str(result)
    )

    try:
        raw = RepeatAssessmentRaw.model_validate(
            payload
        )

    except ValidationError as exc:
        raise RuntimeError(
            f"Repeat assessment failed for "
            f"{issue_id}: {exc}"
        ) from exc

    valid_results = {
        "SAME_FAILURE_MODE",
        "DIFFERENT_FAILURE_MODE",
        "NO_COMPARABLE_HISTORY",
        "UNCERTAIN",
    }

    repeat_result = str(
        raw.Result
    ).strip()

    if (
        repeat_result
        not in valid_results
    ):
        repeat_result = (
            "UNCERTAIN"
        )

    confidence = str(
        raw.Confidence
    ).strip()

    if confidence not in {
        "HIGH",
        "MEDIUM",
        "LOW",
    }:
        confidence = (
            "LOW"
        )

    if (
        raw.Issue_ID
        != issue_id
    ):
        raise RuntimeError(
            f"Repeat assessor returned "
            f"{raw.Issue_ID}; expected {issue_id}"
        )

    return RepeatAssessment(
        Issue_ID=raw.Issue_ID,
        Result=repeat_result,
        Confidence=confidence,
        Reason=str(
            raw.Reason
        ).strip(),
    )