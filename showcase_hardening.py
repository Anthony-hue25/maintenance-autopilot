import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime


RUNTIME = "MaintAutopilot"
UNIT = "U4"

CASES = [
    {
        "name": "Routine repair",
        "case_id": "SHOWCASE-ROUTINE",
        "request": (
            "Hi, the kitchen faucet has a steady drip even when it's fully off. "
            "Not urgent but wanted to report it."
        ),
        "expected_outcome": "ACT",
        "expected_rule": "P15_ROUTINE_AUTHORIZED_ACTION",
    },
    {
        "name": "Needs a detail",
        "case_id": "SHOWCASE-ASK",
        "request": "The second bedroom window doesn't latch.",
        "expected_outcome": "ASK",
        "expected_rule": "P05A_SECURITY_CLARIFICATION",
    },
    {
        "name": "Authority exceeded",
        "case_id": "SHOWCASE-AUTHORITY",
        "request": (
            "The AC isn't cooling. A technician found a failed condensate pump "
            "and quoted $285 to replace it."
        ),
        "expected_outcome": "ESCALATE",
        "expected_rule": "P04_AUTHORITY_EXCEEDED",
    },
    {
        "name": "Critical hazard",
        "case_id": "SHOWCASE-GAS",
        "request": (
            "There is a strong smell of gas and it seems to be getting stronger."
        ),
        "expected_outcome": "ACT+ESCALATE",
        "expected_rule": "P03_CRITICAL_HAZARD",
    },
]


SEMANTIC_FIELDS = [
    "HazardConcepts",
    "ConditionConcepts",
    "InformationState",
    "Predicted_Safety",
    "Predicted_Urgency",
    "Predicted_PrimaryTrade",
    "RepeatAssessment",
    "FailSafeType",
]


def percentile(values, pct):
    if not values:
        return None

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * pct
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower

    return ordered[lower] + (
        ordered[upper] - ordered[lower]
    ) * fraction


def extract_json(stdout):
    """
    AgentCore CLI prints the response JSON plus Session/Log text.
    Find and decode the first complete JSON object.
    """
    decoder = json.JSONDecoder()

    for index, char in enumerate(stdout):
        if char != "{":
            continue

        try:
            obj, _ = decoder.raw_decode(stdout[index:])

            if isinstance(obj, dict):
                return obj

        except json.JSONDecodeError:
            continue

    raise ValueError(
        "No valid JSON response object found in AgentCore output."
    )


def compact(value):
    if value is None:
        return ""

    if isinstance(value, (list, dict)):
        return json.dumps(
            value,
            separators=(",", ":"),
            sort_keys=True,
        )

    return str(value)


def base_result(case, run_number, unique_case_id):
    return {
        "run": run_number,
        "showcase": case["name"],
        "case_id": unique_case_id,
        "expected_outcome": case["expected_outcome"],
        "expected_rule": case["expected_rule"],
        "observed_outcome": "",
        "observed_rule": "",
        "pass": False,
        "latency_ms": "",
        "HazardConcepts": "",
        "ConditionConcepts": "",
        "InformationState": "",
        "Predicted_Safety": "",
        "Predicted_Urgency": "",
        "Predicted_PrimaryTrade": "",
        "RepeatAssessment": "",
        "FailSafeType": "",
        "error": "",
        "raw": "",
    }


def run_case(
    case,
    run_number,
    project_dir,
    payload_path,
    timeout_seconds,
):
    unique_case_id = (
        f"HARDEN-{case['case_id']}-R{run_number:02d}-"
        f"{uuid.uuid4().hex}"
    )

    result = base_result(
        case,
        run_number,
        unique_case_id,
    )

    payload = {
        "request": case["request"],
        "unit": UNIT,
        "clarification": "",
        "case_id": unique_case_id,
    }

    with open(
        payload_path,
        "w",
        encoding="ascii",
    ) as handle:
        json.dump(
            payload,
            handle,
            ensure_ascii=True,
        )

    command = (
        f'agentcore invoke '
        f'--runtime {RUNTIME} '
        f'--prompt-file "{payload_path}"'
    )

    started = time.perf_counter()

    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                command,
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )

        latency_ms = round(
            (time.perf_counter() - started) * 1000,
            1,
        )

        result["latency_ms"] = latency_ms

        raw_output = completed.stdout

        if completed.stderr:
            raw_output += (
                "\n\n--- STDERR ---\n"
                + completed.stderr
            )

        result["raw"] = raw_output

        if completed.returncode != 0:
            result["error"] = (
                f"agentcore exit code "
                f"{completed.returncode}"
            )
            return result

        response = extract_json(completed.stdout)

        observed_outcome = response.get(
            "PolicyOutcome",
            "",
        )

        observed_rule = response.get(
            "PolicyRule",
            "",
        )

        result["observed_outcome"] = observed_outcome
        result["observed_rule"] = observed_rule

        for field in SEMANTIC_FIELDS:
            result[field] = compact(
                response.get(field)
            )

        passed = (
            observed_outcome
            == case["expected_outcome"]
            and observed_rule
            == case["expected_rule"]
        )

        result["pass"] = passed

        if not passed:
            result["error"] = (
                "Outcome/rule mismatch"
            )

        return result

    except subprocess.TimeoutExpired as exc:
        latency_ms = round(
            (time.perf_counter() - started) * 1000,
            1,
        )

        result["latency_ms"] = latency_ms
        result["error"] = (
            f"Timeout after {timeout_seconds}s"
        )

        stdout = exc.stdout or ""
        stderr = exc.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode(
                errors="replace"
            )

        if isinstance(stderr, bytes):
            stderr = stderr.decode(
                errors="replace"
            )

        result["raw"] = (
            stdout
            + "\n\n--- STDERR ---\n"
            + stderr
        )

        return result

    except Exception as exc:
        latency_ms = round(
            (time.perf_counter() - started) * 1000,
            1,
        )

        result["latency_ms"] = latency_ms
        result["error"] = (
            f"{type(exc).__name__}: {exc}"
        )

        return result


def write_failure(
    failure_dir,
    result,
):
    os.makedirs(
        failure_dir,
        exist_ok=True,
    )

    safe_showcase = (
        result["showcase"]
        .replace(" ", "_")
        .replace("/", "_")
    )

    failure_path = os.path.join(
        failure_dir,
        (
            f"run_{result['run']:02d}_"
            f"{safe_showcase}.txt"
        ),
    )

    with open(
        failure_path,
        "w",
        encoding="utf-8",
    ) as handle:
        handle.write(
            f"Showcase: {result['showcase']}\n"
        )
        handle.write(
            f"Case ID: {result['case_id']}\n"
        )
        handle.write(
            f"Expected outcome: "
            f"{result['expected_outcome']}\n"
        )
        handle.write(
            f"Expected rule: "
            f"{result['expected_rule']}\n"
        )
        handle.write(
            f"Observed outcome: "
            f"{result['observed_outcome']}\n"
        )
        handle.write(
            f"Observed rule: "
            f"{result['observed_rule']}\n"
        )
        handle.write(
            f"Error: {result['error']}\n"
        )
        handle.write(
            f"Latency ms: "
            f"{result['latency_ms']}\n"
        )
        handle.write(
            "\n--- RAW RESPONSE ---\n"
        )
        handle.write(
            result.get("raw", "")
        )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Repeated deployed hardening for "
            "Maintenance Autopilot showcase."
        )
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help=(
            "Number of repetitions of all four "
            "showcase cases."
        ),
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help=(
            "Timeout in seconds for each "
            "AgentCore invocation."
        ),
    )

    args = parser.parse_args()

    if args.runs < 1:
        print(
            "ERROR: --runs must be at least 1."
        )
        return 2

    repo_root = os.path.dirname(
        os.path.abspath(__file__)
    )

    project_dir = os.path.join(
        repo_root,
        "MaintAutopilot",
    )

    if not os.path.isdir(project_dir):
        print(
            "ERROR: AgentCore project not found:"
        )
        print(project_dir)
        return 2

    timestamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    results_dir = os.path.join(
        repo_root,
        "hardening_results",
    )

    os.makedirs(
        results_dir,
        exist_ok=True,
    )

    csv_path = os.path.join(
        results_dir,
        (
            f"showcase_hardening_"
            f"{timestamp}.csv"
        ),
    )

    failure_dir = os.path.join(
        results_dir,
        (
            f"showcase_hardening_"
            f"{timestamp}_failures"
        ),
    )

    payload_path = os.path.join(
        project_dir,
        "showcase-hardening-payload.json",
    )

    results = []

    print()
    print(
        "Maintenance Autopilot - "
        "Deployed Showcase Hardening"
    )
    print(f"Runtime: {RUNTIME}")
    print(f"Demo Property: {UNIT}")
    print("Authority: $200")
    print(
        f"Runs per showcase: {args.runs}"
    )
    print(
        "Total planned invocations: "
        f"{args.runs * len(CASES)}"
    )
    print()

    try:
        for run_number in range(
            1,
            args.runs + 1,
        ):
            print(
                f"Run {run_number}/{args.runs}"
            )

            for case in CASES:
                result = run_case(
                    case=case,
                    run_number=run_number,
                    project_dir=project_dir,
                    payload_path=payload_path,
                    timeout_seconds=args.timeout,
                )

                results.append(result)

                marker = (
                    "PASS"
                    if result["pass"]
                    else "FAIL"
                )

                outcome = (
                    result.get(
                        "observed_outcome",
                        "",
                    )
                    or "-"
                )

                rule = (
                    result.get(
                        "observed_rule",
                        "",
                    )
                    or "-"
                )

                latency = result.get(
                    "latency_ms",
                    "",
                )

                print(
                    f"  [{marker}] "
                    f"{case['name']}: "
                    f"{outcome} / {rule} "
                    f"({latency} ms)"
                )

                if not result["pass"]:
                    print(
                        "         Error: "
                        f"{result['error']}"
                    )

                    write_failure(
                        failure_dir,
                        result,
                    )

            print()

    finally:
        try:
            if os.path.exists(payload_path):
                os.remove(payload_path)
        except OSError:
            pass

    fieldnames = [
        "run",
        "showcase",
        "case_id",
        "expected_outcome",
        "expected_rule",
        "observed_outcome",
        "observed_rule",
        "pass",
        "latency_ms",
        "HazardConcepts",
        "ConditionConcepts",
        "InformationState",
        "Predicted_Safety",
        "Predicted_Urgency",
        "Predicted_PrimaryTrade",
        "RepeatAssessment",
        "FailSafeType",
        "error",
    ]

    with open(
        csv_path,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for result in results:
            writer.writerow(
                {
                    key: result.get(key, "")
                    for key in fieldnames
                }
            )

    total = len(results)

    passed = sum(
        1
        for result in results
        if result["pass"]
    )

    failed = total - passed

    errors = sum(
        1
        for result in results
        if result.get("error")
    )

    latencies = [
        result["latency_ms"]
        for result in results
        if isinstance(
            result.get("latency_ms"),
            (int, float),
        )
    ]

    print("=" * 68)
    print("HARDENING SUMMARY")
    print("=" * 68)
    print(
        f"Total invocations : {total}"
    )
    print(
        f"Passed            : {passed}"
    )
    print(
        f"Failed            : {failed}"
    )

    pass_rate = (
        (passed / total * 100)
        if total
        else 0
    )

    print(
        f"Pass rate         : "
        f"{pass_rate:.1f}%"
    )

    print(
        f"Errors/mismatches : {errors}"
    )
    print()

    by_showcase = defaultdict(list)

    for result in results:
        by_showcase[
            result["showcase"]
        ].append(result)

    print("Per showcase:")

    for case in CASES:
        case_results = by_showcase[
            case["name"]
        ]

        case_passes = sum(
            1
            for result in case_results
            if result["pass"]
        )

        print(
            f"  {case['name']}: "
            f"{case_passes}/"
            f"{len(case_results)} passed"
        )

        decision_variants = Counter(
            (
                result.get(
                    "observed_outcome",
                    "",
                ),
                result.get(
                    "observed_rule",
                    "",
                ),
            )
            for result in case_results
        )

        print(
            "    Outcome/rule variants:"
        )

        for (
            outcome,
            rule,
        ), count in decision_variants.items():
            print(
                f"      "
                f"{outcome or '-'} / "
                f"{rule or '-'} : "
                f"{count}"
            )

        semantic_variability = False

        for field in SEMANTIC_FIELDS:
            variants = Counter(
                result.get(field, "")
                for result in case_results
                if result.get(field, "")
            )

            if len(variants) > 1:
                if not semantic_variability:
                    print(
                        "    Semantic variants:"
                    )

                semantic_variability = True

                rendered = "; ".join(
                    (
                        f"{value} "
                        f"({count})"
                    )
                    for value, count
                    in variants.items()
                )

                print(
                    f"      {field}: "
                    f"{rendered}"
                )

        if not semantic_variability:
            print(
                "    Semantic variants:"
            )
            print(
                "      No semantic "
                "variability observed."
            )

    print()

    if latencies:
        print("Latency:")
        print(
            f"  Min    : "
            f"{min(latencies):.0f} ms"
        )
        print(
            f"  Median : "
            f"{statistics.median(latencies):.0f} ms"
        )
        print(
            f"  P95    : "
            f"{percentile(latencies, 0.95):.0f} ms"
        )
        print(
            f"  Max    : "
            f"{max(latencies):.0f} ms"
        )
        print()

    print(
        f"Detailed CSV: {csv_path}"
    )

    if failed:
        print(
            f"Failure evidence: "
            f"{failure_dir}"
        )
        print()
        print(
            "SHOWCASE HARDENING: FAIL"
        )
        return 2

    print()
    print(
        "SHOWCASE HARDENING: PASS"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())