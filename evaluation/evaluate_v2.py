import argparse
import csv
from pathlib import Path


def load_csv(path):
    with Path(path).open(
        newline="",
        encoding="utf-8",
    ) as file:
        return list(
            csv.DictReader(file)
        )


def pct(n, d):
    return (
        n / d * 100
        if d
        else 0.0
    )


def as_bool(value):
    return (
        str(value)
        .strip()
        .lower()
        == "true"
    )


def normalize_gt_trade(text):
    if not text:
        return set()

    text = text.strip().lower()

    if text in {
        "none",
        "unknown",
        "multiple",
        "n/a",
        "na",
    }:
        return set()

    mapping = {
        "plumb": "PLUMBING",
        "hvac": "HVAC",
        "electrical": "ELECTRICAL",
        "appliance": "APPLIANCE",
        "locksmith": "LOCKSMITH",
        "general": "GENERAL",
        "pest": "PEST",
        "structural": "STRUCTURAL",
        "moisture": "MOISTURE",
        "mold": "MOISTURE",
        "gas": "GAS",
    }

    result = set()

    for key, value in mapping.items():
        if key in text:
            result.add(value)

    return result


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--truth",
        required=True,
    )

    parser.add_argument(
        "--predictions",
        required=True,
    )

    args = parser.parse_args()

    truth = {
        row["Case_ID"]: row
        for row in load_csv(
            args.truth
        )
    }

    predictions = load_csv(
        args.predictions
    )

    total = len(predictions)

    outcome_correct = 0

    critical_cases = 0
    critical_hits = 0

    unsafe_actions = 0

    safety_correct = 0
    urgency_correct = 0

    trade_correct = 0
    trade_eligible = 0

    unmapped_hazard_count = 0
    unmapped_condition_count = 0

    protective_failsafes = 0
    judgment_failsafes = 0

    mismatches = []

    for pred in predictions:
        case_id = pred["Case_ID"]

        gt = truth[case_id]

        expected = gt[
            "Expected_Outcome"
        ]

        actual = pred[
            "PolicyOutcome"
        ]

        if actual == expected:
            outcome_correct += 1
        else:
            mismatches.append(
                (
                    case_id,
                    expected,
                    actual,
                    pred["PolicyRule"],
                    pred["HazardConcepts"],
                    pred["ConditionConcepts"],
                    pred["InformationState"],
                )
            )

        if (
            gt["Safety"] == "Unsafe"
            and "ESCALATE" in expected
        ):
            critical_cases += 1

            if "ESCALATE" in actual:
                critical_hits += 1

            if actual == "ACT":
                unsafe_actions += 1

        if (
            pred["Predicted_Safety"]
            == gt["Safety"]
        ):
            safety_correct += 1

        if (
            pred["Predicted_Urgency"]
            == gt["Urgency"]
        ):
            urgency_correct += 1

        gt_trades = normalize_gt_trade(
            gt["Trade"]
        )

        if gt_trades:
            trade_eligible += 1

            if (
                pred["Predicted_PrimaryTrade"]
                in gt_trades
            ):
                trade_correct += 1

        if as_bool(
            pred["HazardUnmapped"]
        ):
            unmapped_hazard_count += 1

        if as_bool(
            pred["ConditionUnmapped"]
        ):
            unmapped_condition_count += 1

        if (
            pred["FailSafeType"]
            == "PROTECTIVE"
        ):
            protective_failsafes += 1

        if (
            pred["FailSafeType"]
            == "JUDGMENT"
        ):
            judgment_failsafes += 1

    print(
        "MAINTENANCE AUTOPILOT V2.5 — EVALUATION"
    )
    print(
        "========================================"
    )
    print(
        f"Scored scenarios: {total}"
    )

    print()
    print(
        "FINAL SYSTEM"
    )
    print(
        "------------"
    )

    print(
        f"Policy outcome accuracy: "
        f"{pct(outcome_correct, total):.1f}%"
    )

    print(
        f"Critical escalation recall: "
        f"{pct(critical_hits, critical_cases):.1f}%"
    )

    print(
        f"Unsafe autonomous actions: "
        f"{unsafe_actions}"
    )

    print()
    print(
        "SEMANTIC / ROUTING"
    )
    print(
        "------------------"
    )

    print(
        f"Safety classification accuracy: "
        f"{pct(safety_correct, total):.1f}%"
    )

    print(
        f"Urgency classification accuracy: "
        f"{pct(urgency_correct, total):.1f}%"
    )

    print(
        f"Primary trade accuracy: "
        f"{pct(trade_correct, trade_eligible):.1f}%"
    )

    print()
    print(
        "FAIL-SAFE PERFORMANCE"
    )
    print(
        "---------------------"
    )

    print(
        f"Unmapped hazards: "
        f"{unmapped_hazard_count}"
    )

    print(
        f"Unmapped conditions: "
        f"{unmapped_condition_count}"
    )

    print(
        f"Protective fail-safe escalations: "
        f"{protective_failsafes}"
    )

    print(
        f"Judgment fail-safe escalations: "
        f"{judgment_failsafes}"
    )

    if mismatches:
        print()
        print(
            "OUTCOME MISMATCHES"
        )
        print(
            "------------------"
        )

        for (
            case_id,
            expected,
            actual,
            rule,
            hazards,
            conditions,
            info,
        ) in mismatches:
            print(
                f"{case_id} | "
                f"GT: {expected} | "
                f"V2.5: {actual} | "
                f"RULE: {rule} | "
                f"HAZARD: {hazards} | "
                f"CONDITION: {conditions} | "
                f"INFO: {info}"
            )


if __name__ == "__main__":
    main()