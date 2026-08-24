import argparse
import csv
from pathlib import Path

from app.tools import PROPERTIES

from app.v2_decompose import (
    decompose_request,
    create_model as create_decompose_model,
)

from app.v2_hazard import (
    assess_hazards,
    create_model as create_hazard_model,
)

from app.v2_hazard_validator import (
    validate_hazards,
)

from app.v2_case import (
    assess_case,
    create_model as create_case_model,
    CaseAssessment,
)

from app.v2_case_validator import (
    validate_case,
)

from app.v2_repeat import (
    assess_repeat,
    create_model as create_repeat_model,
)

from app.v2_policy import (
    apply_policy,
    build_workflow_facts,
)


URGENCY_RANK = {
    "Emergency": 5,
    "Priority": 4,
    "Routine": 3,
    "Cosmetic": 2,
    "None": 1,
    "Unknown": 0,
}


def pipe(values):
    return "|".join(
        str(value)
        for value in values
    )


def load_cases(path):
    with Path(path).open(
        newline="",
        encoding="utf-8",
    ) as file:
        return list(
            csv.DictReader(file)
        )


def get_history(unit):
    return (
        PROPERTIES
        .get(unit, {})
        .get("history", "")
    )


def combine_urgencies(values):
    if not values:
        return "Unknown"

    return max(
        values,
        key=lambda value: URGENCY_RANK.get(
            value,
            0,
        ),
    )


def combine_information_states(values):
    values = set(values)

    if "INSUFFICIENT_AFTER_ASK" in values:
        return "INSUFFICIENT_AFTER_ASK"

    if "NO_RESPONSE_AFTER_ASK" in values:
        return "NO_RESPONSE_AFTER_ASK"

    if "NEEDS_CLARIFICATION" in values:
        return "NEEDS_CLARIFICATION"

    return "SUFFICIENT"


def merge_case_assessments(
    assessments,
    repeat_results,
    case_id,
):
    conditions = []
    infos = []
    urgencies = []
    primary_trades = []
    secondary = []
    evidence = []

    unmapped = False

    for assessment in assessments:
        conditions.extend(
            assessment.ConditionConcepts
        )

        infos.append(
            assessment.InformationState
        )

        urgencies.append(
            assessment.Urgency
        )

        primary_trades.append(
            assessment.PrimaryTrade
        )

        secondary.extend(
            assessment.SecondaryTrades
        )

        evidence.extend(
            assessment.Evidence
        )

        unmapped = (
            unmapped
            or assessment.UnmappedCondition
        )

    # =========================================================
    # REPEAT FAILURE
    #
    # Only the dedicated repeat comparator may inject
    # REPEAT_FAILURE.
    # =========================================================

    if any(
        result.Result == "SAME_FAILURE_MODE"
        for result in repeat_results
    ):
        conditions.append(
            "REPEAT_FAILURE"
        )

    unique_conditions = list(
        dict.fromkeys(
            conditions
        )
    )

    # =========================================================
    # RESOLVED STATE
    #
    # Treat the whole case as resolved only if every decomposed
    # issue says nothing remains.
    # =========================================================

    all_resolved = (
        bool(assessments)
        and all(
            "RESOLVED_NO_OUTSTANDING_NEED"
            in assessment.ConditionConcepts
            for assessment in assessments
        )
    )

    if all_resolved:
        unique_conditions = [
            "RESOLVED_NO_OUTSTANDING_NEED"
        ]

    else:
        unique_conditions = [
            value
            for value in unique_conditions
            if value
            != "RESOLVED_NO_OUTSTANDING_NEED"
        ]

    # =========================================================
    # PRIMARY / SECONDARY TRADE MERGE
    # =========================================================

    primary_trade = (
        primary_trades[0]
        if primary_trades
        else "UNKNOWN"
    )

    for trade in primary_trades[1:]:
        if (
            trade
            not in {
                primary_trade,
                "NONE",
                "UNKNOWN",
            }
            and trade not in secondary
        ):
            secondary.append(
                trade
            )

    secondary = [
        trade
        for trade in dict.fromkeys(
            secondary
        )
        if trade != primary_trade
    ]

    return CaseAssessment(
        Issue_ID=f"{case_id}-MERGED",
        ConditionConcepts=unique_conditions,
        InformationState=combine_information_states(
            infos
        ),
        Urgency=combine_urgencies(
            urgencies
        ),
        PrimaryTrade=primary_trade,
        SecondaryTrades=secondary,
        UnmappedCondition=unmapped,
        UnmappedDescription=None,
        Confidence="MEDIUM",
        Evidence=list(
            dict.fromkeys(
                evidence
            )
        ),
    )


def safety_label(hazard_concepts):
    hazards = set(
        hazard_concepts
    )

    critical = {
        "GAS_HAZARD",
        "CO_HAZARD",
        "ACTIVE_FIRE_OR_SMOKE",
        "ELECTRICAL_HAZARD",
        "WATER_ELECTRICAL_CONTACT",
        "UNCONTROLLED_WATER",
        "SEWAGE_HAZARD",
        "STRUCTURAL_FALL_RISK",
    }

    if hazards.intersection(
        critical
    ):
        return "Unsafe"

    if "SECURITY_EXPOSURE" in hazards:
        return "Potential concern"

    if "UNMAPPED_HAZARD" in hazards:
        return "Uncertain"

    return "Safe"


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

    cases = load_cases(
        args.input
    )

    print()
    print(
        "MAINTENANCE AUTOPILOT V2.5"
    )
    print(
        "========================================"
    )
    print(
        f"Loaded {len(cases)} cases."
    )
    print(
        "Initializing models..."
    )

    hazard_model = (
        create_hazard_model()
    )
    print(
        "Hazard model OK"
    )

    decomposition_model = (
        create_decompose_model()
    )
    print(
        "Decomposition model OK"
    )

    case_model = (
        create_case_model()
    )
    print(
        "Case model OK"
    )

    repeat_model = (
        create_repeat_model()
    )
    print(
        "Repeat model OK"
    )

    predictions = []

    for index, row in enumerate(
        cases,
        start=1,
    ):
        case_id = (
            row.get(
                "Case_ID",
                "",
            )
            .strip()
        )

        unit = (
            row.get(
                "Unit",
                "",
            )
            .strip()
        )

        original_request = (
            row.get(
                "Request",
                "",
            )
            .strip()
        )

        clarification = (
            row.get(
                "Clarification_Response",
                "",
            )
            .strip()
        )

        history = get_history(
            unit
        )

        print()
        print(
            f"Evaluating {case_id} "
            f"({index}/{len(cases)})..."
        )

        # =====================================================
        # 1. FULL-REPORT HAZARD ASSESSMENT
        #
        # This happens before decomposition so cross-symptom
        # hazards cannot be weakened by issue splitting.
        # =====================================================

        hazard = assess_hazards(
            issue_id=f"{case_id}-FULL",
            request=original_request,
            clarification=clarification,
            model=hazard_model,
        )

        # =====================================================
        # 1B. NARROW HAZARD CONTRAST VALIDATOR
        # =====================================================

        hazard = validate_hazards(
            hazard=hazard,
            request=original_request,
            clarification=clarification,
        )

        # =====================================================
        # 2. DETERMINISTIC WORKFLOW FACTS
        #
        # Authority and other deterministic facts must be
        # derived from the original case text.
        # =====================================================

        facts = build_workflow_facts(
            unit=unit,
            request=original_request,
            clarification=clarification,
        )

        # =====================================================
        # 3. ISSUE DECOMPOSITION
        # =====================================================

        decomposition = decompose_request(
            case_id=case_id,
            request=original_request,
            clarification=clarification,
            model=decomposition_model,
        )

        case_assessments = []
        repeat_assessments = []

        # =====================================================
        # 4. PER-ISSUE SEMANTIC ASSESSMENT
        #
        # IMPORTANT:
        # The case validator does NOT run here anymore.
        #
        # Decomposition may remove language that matters to
        # information sufficiency, such as:
        #
        # "I can't work out where it's coming from"
        #
        # or:
        #
        # "funny brown colour"
        #
        # We therefore validate information state only after
        # the issue assessments are merged.
        # =====================================================

        for issue in decomposition.Issues:
            case_assessment = assess_case(
                issue_id=issue.Issue_ID,
                request=issue.Description,
                clarification=clarification,
                maintenance_history=history,
                model=case_model,
            )

            repeat_assessment = assess_repeat(
                issue_id=issue.Issue_ID,
                request=issue.Description,
                clarification=clarification,
                maintenance_history=history,
                model=repeat_model,
            )

            case_assessments.append(
                case_assessment
            )

            repeat_assessments.append(
                repeat_assessment
            )

        # =====================================================
        # 5. MERGE ISSUE-LEVEL RESULTS
        # =====================================================

        merged_case = merge_case_assessments(
            assessments=case_assessments,
            repeat_results=repeat_assessments,
            case_id=case_id,
        )

        # =====================================================
        # 5B. CASE-LEVEL INFORMATION CONTRAST VALIDATION
        #
        # Run against the ORIGINAL tenant report, not the
        # decomposed issue description.
        #
        # This preserves decision-critical wording that issue
        # decomposition may legitimately simplify away.
        # =====================================================

        merged_case = validate_case(
            case=merged_case,
            request=original_request,
            clarification=clarification,
        )

        # =====================================================
        # 6. DETERMINISTIC POLICY
        # =====================================================

        policy = apply_policy(
            hazard=hazard,
            case=merged_case,
            facts=facts,
        )

        predicted_safety = safety_label(
            hazard.HazardConcepts
        )

        # =====================================================
        # 7. OUTPUT RECORD
        # =====================================================

        prediction = {
            "Case_ID": case_id,

            "IssueCount": len(
                decomposition.Issues
            ),

            "MultipleIssues": (
                decomposition.MultipleIssues
            ),

            "HazardConcepts": pipe(
                hazard.HazardConcepts
            ),

            "ConditionConcepts": pipe(
                merged_case.ConditionConcepts
            ),

            "InformationState": (
                merged_case.InformationState
            ),

            "Predicted_Safety": (
                predicted_safety
            ),

            "Predicted_Urgency": (
                merged_case.Urgency
            ),

            "Predicted_PrimaryTrade": (
                merged_case.PrimaryTrade
            ),

            "Predicted_SecondaryTrades": pipe(
                merged_case.SecondaryTrades
            ),

            "RepeatAssessment": pipe(
                [
                    result.Result
                    for result in repeat_assessments
                ]
            ),

            "HazardUnmapped": (
                hazard.UnmappedHazard
            ),

            "ConditionUnmapped": (
                merged_case.UnmappedCondition
            ),

            "FailSafeType": (
                policy.FailSafeType
            ),

            "PolicyOutcome": (
                policy.Outcome
            ),

            "PolicyRule": (
                policy.Rule
            ),
        }

        predictions.append(
            prediction
        )

        print(
            f"{case_id}: "
            f"HAZARD={hazard.HazardConcepts} | "
            f"CONDITION={merged_case.ConditionConcepts} | "
            f"REPEAT="
            f"{[r.Result for r in repeat_assessments]} | "
            f"INFO={merged_case.InformationState} | "
            f"URGENCY={merged_case.Urgency} | "
            f"OUTCOME={policy.Outcome} "
            f"[{policy.Rule}]"
        )

    # =========================================================
    # 8. SAVE OUTPUT
    # =====================================================

    output_path = Path(
        args.output
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "Case_ID",
        "IssueCount",
        "MultipleIssues",
        "HazardConcepts",
        "ConditionConcepts",
        "InformationState",
        "Predicted_Safety",
        "Predicted_Urgency",
        "Predicted_PrimaryTrade",
        "Predicted_SecondaryTrades",
        "RepeatAssessment",
        "HazardUnmapped",
        "ConditionUnmapped",
        "FailSafeType",
        "PolicyOutcome",
        "PolicyRule",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            predictions
        )

    print()
    print(
        f"Saved {len(predictions)} predictions "
        f"to {output_path}"
    )


if __name__ == "__main__":
    main()