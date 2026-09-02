import argparse
import csv
from pathlib import Path

from app.v2_hazard import HazardAssessment
from app.v2_case import CaseAssessment
from app.v2_policy import (
    apply_policy,
    build_workflow_facts,
)


def load_cases(path):
    with Path(path).open(
        newline="",
        encoding="utf-8",
    ) as file:
        return list(csv.DictReader(file))


def contains_any(text, phrases):
    return any(
        phrase in text
        for phrase in phrases
    )


def lexical_hazards(
    case_id,
    request,
    clarification,
):
    text = (
        f"{request} {clarification}"
        .lower()
        .strip()
    )

    hazards = []

    # Deliberately simple lexical matching.
    # No semantic inference or fuzzy matching.

    if contains_any(
        text,
        [
            "smell of gas",
            "smells like gas",
            "gas smell",
            "gas leak",
            "gas escaping",
            "rotten egg smell",
            "rotten-egg smell",
        ],
    ):
        hazards.append("GAS_HAZARD")

    if contains_any(
        text,
        [
            "carbon monoxide",
            "co alarm",
            "co detector",
        ],
    ):
        hazards.append("CO_HAZARD")

    if contains_any(
        text,
        [
            "smoke",
            "on fire",
            "flames",
            "burning",
        ],
    ):
        hazards.append(
            "ACTIVE_FIRE_OR_SMOKE"
        )

    if contains_any(
        text,
        [
            "sparking",
            "sparks",
            "exposed wire",
            "exposed wiring",
            "electrical shock",
            "electric shock",
            "breaker tripped",
            "breaker keeps tripping",
            "burning outlet",
            "burning socket",
            "smoke from the electrical",
            "smoke from electrical",
        ],
    ):
        hazards.append(
            "ELECTRICAL_HAZARD"
        )

    water_words = contains_any(
        text,
        [
            "water",
            "leak",
            "leaking",
            "flood",
            "flooding",
            "dripping",
        ],
    )

    electrical_words = contains_any(
        text,
        [
            "outlet",
            "socket",
            "electrical",
            "electric",
            "wiring",
            "breaker",
        ],
    )

    if water_words and electrical_words:
        hazards.append(
            "WATER_ELECTRICAL_CONTACT"
        )

    if contains_any(
        text,
        [
            "flooding",
            "pouring water",
            "water pouring",
            "can't stop the water",
            "cannot stop the water",
            "burst pipe",
            "overflowing onto",
        ],
    ):
        hazards.append(
            "UNCONTROLLED_WATER"
        )

    if contains_any(
        text,
        [
            "sewage",
            "sewer backup",
            "sewage backup",
            "wastewater",
        ],
    ):
        hazards.append(
            "SEWAGE_HAZARD"
        )

    if contains_any(
        text,
        [
            "loose handrail",
            "wobbly handrail",
            "collapse",
            "fall hazard",
            "railing is loose",
            "rail is loose",
        ],
    ):
        hazards.append(
            "STRUCTURAL_FALL_RISK"
        )

    security_object = contains_any(
        text,
        [
            "door",
            "window",
            "lock",
            "latch",
        ],
    )

    cannot_secure = contains_any(
        text,
        [
            "won't lock",
            "will not lock",
            "cannot lock",
            "can't lock",
            "doesn't lock",
            "does not lock",
            "cannot secure",
            "can't secure",
            "won't secure",
            "cannot be secured",
        ],
    )

    accessible = contains_any(
        text,
        [
            "front door",
            "main door",
            "main entrance",
            "entrance door",
            "ground floor",
            "ground-floor",
            "street-facing",
            "externally accessible",
        ],
    )

    if (
        security_object
        and cannot_secure
        and accessible
    ):
        hazards.append(
            "SECURITY_EXPOSURE"
        )

    hazards = list(
        dict.fromkeys(hazards)
    )

    if not hazards:
        hazards = [
            "NO_ACTIVE_HAZARD"
        ]

    return HazardAssessment(
        Issue_ID=f"{case_id}-LEXICAL",
        HazardConcepts=hazards,
        UnmappedHazard=False,
        UnmappedDescription=None,
        Confidence="LOW",
        Evidence=[],
    )


def lexical_case(
    case_id,
    request,
    clarification,
):
    text = (
        f"{request} {clarification}"
        .lower()
        .strip()
    )

    conditions = []

    resolved = contains_any(
        text,
        [
            "nothing remains",
            "no maintenance defect remains",
            "working again",
            "started working again",
            "problem is resolved",
            "issue is resolved",
            "fixed itself",
            "false alarm",
        ],
    )

    if resolved:
        return CaseAssessment(
            Issue_ID=f"{case_id}-LEXICAL",
            ConditionConcepts=[
                "RESOLVED_NO_OUTSTANDING_NEED"
            ],
            InformationState="SUFFICIENT",
            Urgency="None",
            PrimaryTrade="NONE",
            SecondaryTrades=[],
            UnmappedCondition=False,
            UnmappedDescription=None,
            Confidence="LOW",
            Evidence=[],
        )

    conditions.append(
        "ACTIVE_MAINTENANCE_NEED"
    )

    moisture = contains_any(
        text,
        [
            "water",
            "leak",
            "leaking",
            "damp",
            "moisture",
            "stain",
            "wet",
            "puddle",
            "flood",
        ],
    )

    if moisture:
        conditions.append(
            "MOISTURE_PRESENT"
        )

    if contains_any(
        text,
        [
            "soaked the cabinet",
            "soaked cabinet",
            "soaked the floor",
            "soaked flooring",
            "damaged the ceiling",
            "damaged the wall",
            "property damage",
        ],
    ):
        conditions.append(
            "PROPERTY_DAMAGE"
        )

    if moisture and contains_any(
        text,
        [
            "soft",
            "softened",
            "swollen",
            "warped",
            "sagging",
            "crumbling",
            "delamination",
            "rotted",
            "rot ",
            "deteriorated",
        ],
    ):
        conditions.append(
            "MATERIAL_MOISTURE_DAMAGE"
        )

    mold_present = contains_any(
        text,
        [
            "mold",
            "mould",
        ],
    )

    mold_progressing = contains_any(
        text,
        [
            "spreading",
            "getting bigger",
            "doubled in size",
            "worsening",
            "growing",
        ],
    )

    if mold_present and mold_progressing:
        conditions.append(
            "MOLD_SPREAD"
        )

    if contains_any(
        text,
        [
            "upgrade",
            "better model",
            "replace it with",
            "prefer the better",
            "smart thermostat",
            "repair or replace",
        ],
    ):
        conditions.append(
            "REPLACEMENT_OR_UPGRADE"
        )

    if contains_any(
        text,
        [
            "same problem again",
            "same issue again",
            "happened again",
            "keeps happening",
            "failed again",
        ],
    ):
        conditions.append(
            "REPEAT_FAILURE"
        )

    if contains_any(
        text,
        [
            "wasp",
            "hornet",
            "bee nest",
            "rodent",
            "rats",
            "mice",
            "infestation",
        ],
    ):
        conditions.append(
            "PEST_ACTIVITY"
        )

    security_uncertain = (
        contains_any(
            text,
            [
                "lock is being weird",
                "lock feels weird",
                "doesn't latch",
                "does not latch",
                "won't latch",
                "will not latch",
            ],
        )
        and not contains_any(
            text,
            [
                "still locks",
                "can still lock",
                "ground floor",
                "ground-floor",
                "street-facing",
                "externally accessible",
            ],
        )
    )

    if security_uncertain:
        conditions.append(
            "SECURITY_STATUS_UNRESOLVED"
        )

    # Information state:
    # intentionally narrow lexical approximation.

    no_response = contains_any(
        text,
        [
            "no response",
            "no reply",
            "did not respond",
            "didn't respond",
            "no answer",
        ],
    )

    clarification_present = bool(
        clarification.strip()
    )

    unclear = contains_any(
        text,
        [
            "not sure",
            "don't know",
            "do not know",
            "can't tell",
            "cannot tell",
            "somewhere",
            "can't work out",
            "cannot work out",
            "unknown",
        ],
    )

    if no_response:
        information_state = (
            "NO_RESPONSE_AFTER_ASK"
        )

    elif security_uncertain:
        if clarification_present:
            information_state = (
                "INSUFFICIENT_AFTER_ASK"
            )
        else:
            information_state = (
                "NEEDS_CLARIFICATION"
            )

    elif unclear:
        if clarification_present:
            information_state = (
                "INSUFFICIENT_AFTER_ASK"
            )
        else:
            information_state = (
                "NEEDS_CLARIFICATION"
            )

    else:
        information_state = "SUFFICIENT"

    # Trade routing

    trade_map = [
        (
            "PLUMBING",
            [
                "faucet",
                "tap",
                "toilet",
                "pipe",
                "plumbing",
                "sink",
                "water bill",
                "drain",
            ],
        ),
        (
            "HVAC",
            [
                "air conditioning",
                "air conditioner",
                "a/c",
                " ac ",
                "hvac",
                "thermostat",
            ],
        ),
        (
            "ELECTRICAL",
            [
                "electrical",
                "outlet",
                "socket",
                "breaker",
                "wiring",
                "light switch",
            ],
        ),
        (
            "APPLIANCE",
            [
                "washing machine",
                "dishwasher",
                "fridge",
                "refrigerator",
                "oven",
                "stove",
                "disposal",
            ],
        ),
        (
            "LOCKSMITH",
            [
                "lock",
                "key",
                "latch",
            ],
        ),
        (
            "PEST",
            [
                "wasp",
                "hornet",
                "bee nest",
                "rodent",
                "rats",
                "mice",
                "infestation",
            ],
        ),
        (
            "STRUCTURAL",
            [
                "handrail",
                "railing",
                "stairs",
                "balcony",
                "structural",
            ],
        ),
        (
            "MOISTURE",
            [
                "mold",
                "mould",
                "damp",
                "moisture",
            ],
        ),
        (
            "GAS",
            [
                "gas",
            ],
        ),
    ]

    primary_trade = "GENERAL"

    for trade, phrases in trade_map:
        if contains_any(text, phrases):
            primary_trade = trade
            break

    # Very simple urgency approximation.

    if contains_any(
        text,
        [
            "fire",
            "smoke",
            "sparking",
            "gas leak",
            "smell of gas",
            "flooding",
            "pouring water",
            "sewage",
            "collapse",
        ],
    ):
        urgency = "Emergency"

    elif contains_any(
        text,
        [
            "leak",
            "running toilet",
            "won't open",
            "will not open",
            "stuck",
            "wasp",
            "hornet",
            "mold",
            "mould",
        ],
    ):
        urgency = "Priority"

    elif contains_any(
        text,
        [
            "cosmetic",
            "paint",
            "scratch",
            "scuff",
        ],
    ):
        urgency = "Cosmetic"

    else:
        urgency = "Routine"

    return CaseAssessment(
        Issue_ID=f"{case_id}-LEXICAL",
        ConditionConcepts=list(
            dict.fromkeys(conditions)
        ),
        InformationState=information_state,
        Urgency=urgency,
        PrimaryTrade=primary_trade,
        SecondaryTrades=[],
        UnmappedCondition=False,
        UnmappedDescription=None,
        Confidence="LOW",
        Evidence=[],
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
    )

    parser.add_argument(
        "--output",
        required=True,
    )

    args = parser.parse_args()

    cases = load_cases(args.input)
    predictions = []

    for row in cases:
        case_id = (
            row.get("Case_ID", "")
            .strip()
        )

        unit = (
            row.get("Unit", "")
            .strip()
        )

        request = (
            row.get("Request", "")
            .strip()
        )

        clarification = (
            row.get(
                "Clarification_Response",
                "",
            )
            .strip()
        )

        hazard = lexical_hazards(
            case_id,
            request,
            clarification,
        )

        case = lexical_case(
            case_id,
            request,
            clarification,
        )

        facts = build_workflow_facts(
            unit=unit,
            request=request,
            clarification=clarification,
        )

        policy = apply_policy(
            hazard=hazard,
            case=case,
            facts=facts,
        )

        predictions.append(
            {
                "Case_ID": case_id,
                "PolicyOutcome": policy.Outcome,
                "PolicyRule": policy.Rule,
                "HazardConcepts": "|".join(
                    hazard.HazardConcepts
                ),
                "ConditionConcepts": "|".join(
                    case.ConditionConcepts
                ),
                "InformationState": (
                    case.InformationState
                ),
            }
        )

    output_path = Path(args.output)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "Case_ID",
                "PolicyOutcome",
                "PolicyRule",
                "HazardConcepts",
                "ConditionConcepts",
                "InformationState",
            ],
        )

        writer.writeheader()
        writer.writerows(predictions)

    print(
        f"Saved {len(predictions)} "
        f"baseline predictions to "
        f"{output_path}"
    )


if __name__ == "__main__":
    main()