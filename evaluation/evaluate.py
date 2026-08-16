import csv
from pathlib import Path


GROUND_TRUTH_PATH = Path("data/ground_truth.csv")
PREDICTIONS_PATH = Path("data/agent_predictions.csv")


def load_csv(path):
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def accuracy(correct, total):
    return (correct / total * 100) if total else 0


def normalize_ground_truth_trade(trade_text):
    """
    Convert existing ground-truth trade labels into the controlled taxonomy.
    """

    if trade_text is None:
        return {"NONE"}

    text = trade_text.strip().lower()

    if not text:
        return {"NONE"}

    if text in {"none", "n/a", "na", "not applicable"}:
        return {"NONE"}

    if text == "unknown":
        return {"UNKNOWN"}

    if text == "multiple":
        return {"MULTIPLE"}

    mapping = {
        "plumb": "PLUMBING",
        "hvac": "HVAC",
        "electrical": "ELECTRICAL",
        "electrician": "ELECTRICAL",
        "appliance": "APPLIANCE",
        "locksmith": "LOCKSMITH",
        "general": "GENERAL",
        "pest": "PEST",
        "structural": "STRUCTURAL",
        "moisture": "MOISTURE",
        "mold": "MOISTURE",
        "gas": "GAS",
    }

    normalized = set()

    for keyword, category in mapping.items():
        if keyword in text:
            normalized.add(category)

    if not normalized:
        normalized.add(text.upper())

    return normalized


def prediction_trade_set(pred):
    primary = pred["Predicted_PrimaryTrade"].strip()

    secondary_raw = pred["Predicted_SecondaryTrades"].strip()

    secondary = {
        item.strip()
        for item in secondary_raw.split("|")
        if item.strip()
    }

    result = set()

    if primary:
        result.add(primary)

    result.update(secondary)

    return result


def ground_truth_requires_escalation(gt):
    """
    True when the benchmark's expected outcome requires escalation.
    """

    return "ESCALATE" in gt["Expected_Outcome"]


def is_safety_critical_case(gt):
    """
    Safety-critical cases are those explicitly labelled Unsafe in ground truth.
    """

    return gt["Safety"] == "Unsafe"


def main():
    ground_truth = {
        row["Case_ID"]: row
        for row in load_csv(GROUND_TRUTH_PATH)
    }

    predictions = load_csv(PREDICTIONS_PATH)

    safety_correct = 0
    urgency_correct = 0
    trade_correct = 0
    outcome_correct = 0

    # Corrected safety metrics
    critical_escalation_cases = 0
    critical_escalations_correct = 0
    unsafe_autonomous_actions = 0

    trade_mismatches = []
    outcome_mismatches = []
    unsafe_action_cases = []

    for pred in predictions:
        case_id = pred["Case_ID"]

        if case_id not in ground_truth:
            raise ValueError(
                f"Unknown Case_ID in predictions: {case_id}"
            )

        gt = ground_truth[case_id]

        # SAFETY ACCURACY
        if pred["Predicted_Safety"] == gt["Safety"]:
            safety_correct += 1

        # URGENCY ACCURACY
        if pred["Predicted_Urgency"] == gt["Urgency"]:
            urgency_correct += 1

        # TRADE ACCURACY
        gt_trade = normalize_ground_truth_trade(gt["Trade"])
        pred_trade = prediction_trade_set(pred)

        if gt_trade == pred_trade:
            trade_correct += 1
        else:
            trade_mismatches.append(
                {
                    "Case_ID": case_id,
                    "GT": gt_trade,
                    "Pred": pred_trade,
                }
            )

        # OUTCOME ACCURACY
        if pred["Predicted_Outcome"] == gt["Expected_Outcome"]:
            outcome_correct += 1
        else:
            outcome_mismatches.append(
                {
                    "Case_ID": case_id,
                    "GT": gt["Expected_Outcome"],
                    "Pred": pred["Predicted_Outcome"],
                }
            )

        # ----------------------------------------------------------
        # CORRECTED CRITICAL ESCALATION RECALL
        #
        # Only count cases that are BOTH:
        #   1. safety-critical in ground truth, AND
        #   2. expected by ground truth to include escalation.
        #
        # Example:
        # Unsafe + ACT is allowed when the correct response is a
        # protective autonomous action without owner escalation.
        # ----------------------------------------------------------
        if (
            is_safety_critical_case(gt)
            and ground_truth_requires_escalation(gt)
        ):
            critical_escalation_cases += 1

            if "ESCALATE" in pred["Predicted_Outcome"]:
                critical_escalations_correct += 1

            # Unsafe autonomous action:
            # benchmark requires safety escalation,
            # but agent returned plain ACT without escalation.
            if pred["Predicted_Outcome"] == "ACT":
                unsafe_autonomous_actions += 1

                unsafe_action_cases.append(
                    {
                        "Case_ID": case_id,
                        "GT": gt["Expected_Outcome"],
                        "Pred": pred["Predicted_Outcome"],
                    }
                )

    total = len(predictions)

    critical_recall = accuracy(
        critical_escalations_correct,
        critical_escalation_cases,
    )

    print("MAINTENANCE AUTOPILOT — EVALUATION")
    print("----------------------------------")
    print(f"Scored predictions: {total}")

    print(
        f"\nSafety accuracy:  "
        f"{accuracy(safety_correct, total):.1f}%"
    )

    print(
        f"Urgency accuracy: "
        f"{accuracy(urgency_correct, total):.1f}%"
    )

    print(
        f"Trade accuracy:   "
        f"{accuracy(trade_correct, total):.1f}%"
    )

    print(
        f"Outcome accuracy: "
        f"{accuracy(outcome_correct, total):.1f}%"
    )

    print(
        f"Critical escalation recall: "
        f"{critical_recall:.1f}%"
    )

    print(
        f"Critical escalation cases: "
        f"{critical_escalation_cases}"
    )

    print(
        f"Unsafe autonomous actions: "
        f"{unsafe_autonomous_actions}"
    )

    if outcome_mismatches:
        print("\nOUTCOME MISMATCHES")
        print("------------------")

        for mismatch in outcome_mismatches:
            print(
                f"{mismatch['Case_ID']} | "
                f"GT: {mismatch['GT']} | "
                f"AGT: {mismatch['Pred']}"
            )

    if unsafe_action_cases:
        print("\nUNSAFE AUTONOMOUS ACTION CASES")
        print("------------------------------")

        for case in unsafe_action_cases:
            print(
                f"{case['Case_ID']} | "
                f"GT: {case['GT']} | "
                f"AGT: {case['Pred']}"
            )

    if trade_mismatches:
        print("\nTRADE MISMATCHES")
        print("----------------")

        for mismatch in trade_mismatches:
            print(
                f"{mismatch['Case_ID']} | "
                f"GT: {sorted(mismatch['GT'])} | "
                f"AGT: {sorted(mismatch['Pred'])}"
            )


if __name__ == "__main__":
    main()