from app.v2_agent import (
    get_history,
    merge_case_assessments,
    safety_label,
)

from app.v2_decompose import (
    decompose_request,
    create_model as create_decompose_model,
)

from app.v2_hazard import (
    assess_hazards,
    create_model as create_hazard_model,
)

from app.v2_hazard_validator import validate_hazards

from app.v2_case import (
    assess_case,
    create_model as create_case_model,
)

from app.v2_case_validator import validate_case

from app.v2_repeat import (
    assess_repeat,
    create_model as create_repeat_model,
)

from app.v2_policy import (
    apply_policy,
    build_workflow_facts,
)


class MaintenanceAutopilotRuntime:
    """
    Thin runtime adapter around the frozen Maintenance Autopilot V2.5 engine.

    Semantic interpretation remains in the existing Strands/Bedrock modules.
    Authority remains in the existing deterministic policy.
    """

    def __init__(self):
        self.hazard_model = create_hazard_model()
        self.decomposition_model = create_decompose_model()
        self.case_model = create_case_model()
        self.repeat_model = create_repeat_model()

    def evaluate(
        self,
        request: str,
        unit: str = "",
        clarification: str = "",
        case_id: str = "LIVE",
    ) -> dict:

        request = (request or "").strip()
        unit = (unit or "").strip()
        clarification = (clarification or "").strip()
        case_id = (case_id or "LIVE").strip()

        if not request:
            raise ValueError("request must be a non-empty string")

        history = get_history(unit)

        # 1. Full-report hazard assessment
        hazard = assess_hazards(
            issue_id=f"{case_id}-FULL",
            request=request,
            clarification=clarification,
            model=self.hazard_model,
        )

        # 1B. Hazard contrast validator
        hazard = validate_hazards(
            hazard=hazard,
            request=request,
            clarification=clarification,
        )

        # 2. Deterministic workflow facts
        facts = build_workflow_facts(
            unit=unit,
            request=request,
            clarification=clarification,
        )

        # 3. Issue decomposition
        decomposition = decompose_request(
            case_id=case_id,
            request=request,
            clarification=clarification,
            model=self.decomposition_model,
        )

        case_assessments = []
        repeat_assessments = []

        # 4. Per-issue semantic assessment
        for issue in decomposition.Issues:
            case_assessment = assess_case(
                issue_id=issue.Issue_ID,
                request=issue.Description,
                clarification=clarification,
                maintenance_history=history,
                model=self.case_model,
            )

            repeat_assessment = assess_repeat(
                issue_id=issue.Issue_ID,
                request=issue.Description,
                clarification=clarification,
                maintenance_history=history,
                model=self.repeat_model,
            )

            case_assessments.append(case_assessment)
            repeat_assessments.append(repeat_assessment)

        # 5. Merge issue-level results
        merged_case = merge_case_assessments(
            assessments=case_assessments,
            repeat_results=repeat_assessments,
            case_id=case_id,
        )

        # 5B. Case-level information contrast validation
        merged_case = validate_case(
            case=merged_case,
            request=request,
            clarification=clarification,
        )

        # 6. Deterministic policy
        policy = apply_policy(
            hazard=hazard,
            case=merged_case,
            facts=facts,
        )

        predicted_safety = safety_label(
            hazard.HazardConcepts
        )

        # 7. Structured runtime response
        return {
            "Case_ID": case_id,
            "IssueCount": len(decomposition.Issues),
            "MultipleIssues": decomposition.MultipleIssues,
            "HazardConcepts": hazard.HazardConcepts,
            "ConditionConcepts": merged_case.ConditionConcepts,
            "InformationState": merged_case.InformationState,
            "Predicted_Safety": predicted_safety,
            "Predicted_Urgency": merged_case.Urgency,
            "Predicted_PrimaryTrade": merged_case.PrimaryTrade,
            "Predicted_SecondaryTrades": merged_case.SecondaryTrades,
            "RepeatAssessment": [
                result.Result
                for result in repeat_assessments
            ],
            "HazardUnmapped": hazard.UnmappedHazard,
            "ConditionUnmapped": merged_case.UnmappedCondition,
            "FailSafeType": policy.FailSafeType,
            "PolicyOutcome": policy.Outcome,
            "PolicyRule": policy.Rule,
        }
