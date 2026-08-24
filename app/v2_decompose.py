import json
import re

from pydantic import BaseModel, Field, ValidationError
from strands import Agent
from strands.models import BedrockModel


class IssueItem(BaseModel):
    Issue_ID: str
    Description: str


class DecompositionRaw(BaseModel):
    Case_ID: str
    MultipleIssues: bool = False
    Issues: list[IssueItem] = Field(default_factory=list)


DECOMPOSE_SYSTEM_PROMPT = """
You are the issue-decomposition component of Maintenance Autopilot.

Your ONLY job is to determine whether one tenant message contains
multiple DISTINCT maintenance issues.

You do NOT:
- assess safety
- assess urgency
- choose a trade
- decide ACT / ESCALATE / ASK / AWAITING / CLOSE
- interpret policy

------------------------------------------------------------
RULE
------------------------------------------------------------

If the message contains one maintenance issue:
return exactly one issue.

If it contains multiple distinct maintenance issues:
split them into independent issue descriptions.

Do NOT split:
- symptoms that are clearly part of the same failure
- a hazard and its obvious associated equipment symptom when they form
  one incident
- contextual details from the actual defect

Examples:

"Oven isn't heating and bathroom fan is noisy"
= two issues.

"Gas odor by the stove and stove igniter won't work"
may be treated as one related gas/stove incident if the symptoms are
part of the same event.

"Dishwasher leaked and the floor is swelling"
= one source issue plus consequential damage, not two independent
maintenance requests.

Return ONLY JSON:

{
  "Case_ID": "GT-001",
  "MultipleIssues": false,
  "Issues": [
    {
      "Issue_ID": "GT-001-I1",
      "Description": "Kitchen faucet is dripping."
    }
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
            raise ValueError("Decomposition JSON must be an object.")

        return result

    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end <= start:
        raise ValueError(
            "Could not locate decomposition JSON.\n"
            f"Raw response:\n{cleaned}"
        )

    return json.loads(
        cleaned[start:end + 1]
    )


def decompose_request(
    case_id: str,
    request: str,
    clarification: str = "",
    model=None,
) -> DecompositionRaw:

    if model is None:
        model = create_model()

    agent = Agent(
        model=model,
        system_prompt=DECOMPOSE_SYSTEM_PROMPT,
        callback_handler=None,
    )

    clarification_text = (
        clarification.strip()
        if clarification.strip()
        else "None provided"
    )

    prompt = f"""
Case_ID:
{case_id}

Tenant request:
{request}

Clarification / follow-up:
{clarification_text}

Split only genuinely distinct maintenance issues.

Return JSON only.
"""

    result = agent(prompt)

    payload = extract_json(
        str(result)
    )

    try:
        parsed = DecompositionRaw.model_validate(
            payload
        )

    except ValidationError as exc:
        raise RuntimeError(
            f"Decomposition failed for {case_id}: {exc}"
        ) from exc

    if parsed.Case_ID != case_id:
        raise RuntimeError(
            f"Decomposer returned {parsed.Case_ID}; "
            f"expected {case_id}"
        )

    if not parsed.Issues:
        parsed.Issues = [
            IssueItem(
                Issue_ID=f"{case_id}-I1",
                Description=request,
            )
        ]

        parsed.MultipleIssues = False

    return parsed