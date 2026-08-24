import csv
from pathlib import Path

from strands import Agent
from strands.models import BedrockModel

from app.agent import (
    MaintenanceDecision,
    SYSTEM_PROMPT,
    build_guardrails,
    build_case_prompt,
    resolve_outcome,
)

from app.tools import (
    get_property_details,
    check_repair_authority,
)


HOLDOUT_PATH = Path("data/holdout_validation.csv")
PREDICTIONS_PATH = Path("data/holdout_predictions.csv")


def load_holdout():
    with HOLDOUT_PATH.open(
        newline="",
        encoding="utf-8",
    ) as file:
        return list(csv.DictReader(file))


def main():
    model = BedrockModel(
        model_id="us.amazon.nova-2-lite-v1:0",
        region_name="us-east-1",
        temperature=0,
    )

    cases = load_holdout()

    print(
        "\nMAINTENANCE AUTOPILOT — SEALED HOLDOUT RUN"
    )
    print(
        "=========================================="
    )
    print(
        f"Loaded {len(cases)} holdout cases."
    )
    print(
        "Frozen agent + governor. No tuning."
    )

    predictions = []

    for index, row in enumerate(cases, start=1):
        print(
            f"\nEvaluating {row['Case_ID']} "
            f"({index}/{len(cases)})..."
        )

        guardrails = build_guardrails(row)

        # Fresh agent for every case.
        # No conversation history is carried between cases.
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

        governed_outcome = resolve_outcome(
            row,
            decision,
            guardrails,
        )

        governor_intervened = (
            raw_outcome != governed_outcome
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
                "Governor_Outcome": governed_outcome,
                "Governor_Intervened": governor_intervened,
                "Reason": decision.Reason,
            }
        )

        marker = (
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
            f"GOV={governed_outcome}"
            f"{marker}"
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
        "\n=========================================="
    )
    print(
        f"Saved {len(predictions)} holdout predictions to "
        f"{PREDICTIONS_PATH}"
    )


if __name__ == "__main__":
    main()