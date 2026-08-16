TARGET_CASES = {
    # Original five failures
    "GT-037": "ACT",
    "GT-040": "ASK",
    "GT-043": "ACT+ESCALATE",
    "GT-050": "ESCALATE",
    "GT-060": "ACT+ESCALATE",

    # Original protected controls
    "GT-003": "ACT+ESCALATE",
    "GT-007": "ESCALATE",
    "GT-014": "ACT",
    "GT-023": "ACT+ESCALATE",
    "GT-027": "ACT",

    # Seven failures from independent 61-case run
    "GT-010": "ESCALATE",
    "GT-016": "ACT+ESCALATE",
    "GT-019": "ESCALATE",
    "GT-020": "ASK",
    "GT-024": "ACT",
    "GT-029": "ACT+ESCALATE",
    "GT-035": "ESCALATE",
}


def main():
    import csv
    from pathlib import Path

    predictions_path = Path(
        "data/agent_predictions.csv"
    )

    with predictions_path.open(
        newline="",
        encoding="utf-8",
    ) as file:
        predictions = {
            row["Case_ID"]: row
            for row in csv.DictReader(file)
        }

    passed = 0

    print(
        "MAINTENANCE AUTOPILOT — REGRESSION GATE"
    )
    print(
        "---------------------------------------"
    )

    for case_id, expected in TARGET_CASES.items():
        if case_id not in predictions:
            print(
                f"{case_id}: MISSING"
            )
            continue

        actual = predictions[
            case_id
        ]["Predicted_Outcome"]

        ok = actual == expected

        status = (
            "PASS"
            if ok
            else "FAIL"
        )

        print(
            f"{case_id}: {status} | "
            f"Expected: {expected} | "
            f"Actual: {actual}"
        )

        if ok:
            passed += 1

    total = len(TARGET_CASES)

    print(
        "\n---------------------------------------"
    )
    print(
        f"Passed: {passed}/{total}"
    )

    if passed == total:
        print(
            "REGRESSION GATE: PASS"
        )
    else:
        print(
            "REGRESSION GATE: FAIL"
        )


if __name__ == "__main__":
    main()