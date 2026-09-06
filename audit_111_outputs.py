import csv
import html
import json
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "audit_111_outputs.html"
TEMP = ROOT / "_audit_111_renderer.js"


def read_csv(path):
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        return list(csv.DictReader(f))


def index_by_case(rows):
    return {
        row["Case_ID"]: row
        for row in rows
    }


def split_pipe(value):
    if not value:
        return []

    return [
        item.strip()
        for item in value.split("|")
        if item.strip()
    ]


# ---------------------------------------------------------
# LOAD SOURCE CASES AND FROZEN V2.5 PREDICTIONS
# ---------------------------------------------------------

gt_source = index_by_case(
    read_csv(DATA / "ground_truth.csv")
)

gt_predictions = read_csv(
    DATA / "v2_5_step5_61.csv"
)

hb_source = index_by_case(
    read_csv(DATA / "holdout_v2_validation.csv")
)

hb_predictions = read_csv(
    DATA / "v2_5_step5_B.csv"
)


combined = []


for prediction in gt_predictions:
    case_id = prediction["Case_ID"]
    source = gt_source.get(case_id)

    if not source:
        raise RuntimeError(
            f"Missing source case: {case_id}"
        )

    combined.append(
        (source, prediction, "GT")
    )


for prediction in hb_predictions:
    case_id = prediction["Case_ID"]
    source = hb_source.get(case_id)

    if not source:
        raise RuntimeError(
            f"Missing source case: {case_id}"
        )

    combined.append(
        (source, prediction, "HB")
    )


if len(combined) != 111:
    raise RuntimeError(
        f"Expected exactly 111 cases, "
        f"found {len(combined)}"
    )


# ---------------------------------------------------------
# RUN THE ACTUAL CURRENT PRESENTATION.JS
#
# Important:
# ConditionConcepts is passed to the renderer.
#
# Clarification_Response is NOT interpreted here.
# It is displayed later for human audit context only.
# ---------------------------------------------------------

renderer_script = r'''
"use strict";

const fs = require("fs");
const presentation =
  require("./web/presentation.js");

const rows = JSON.parse(
  fs.readFileSync(0, "utf8")
);

function splitPipe(value) {
  return String(value || "")
    .split("|")
    .map(value => value.trim())
    .filter(Boolean);
}

const rendered = rows.map(row => {
  const p = row.prediction;

  const result = {
    decision: p.PolicyOutcome || "",

    technical: {
      hazard:
        splitPipe(p.HazardConcepts),

      condition:
        splitPipe(p.ConditionConcepts),

      urgency:
        p.Predicted_Urgency || "",

      trade:
        p.Predicted_PrimaryTrade || "",

      information:
        p.InformationState || ""
    }
  };

  const interpretation =
    presentation.buildHumanInterpretation(
      result
    );

  const outcome =
    presentation.buildOutcomePresentation(
      p.PolicyOutcome
    );

  const why =
    presentation.buildBoundaryExplanation(
      result
    );

  return {
    case_id: row.case_id,
    title: interpretation.title,
    description:
      interpretation.description,
    next_action: outcome.label,
    supporting: outcome.supporting,
    attention: outcome.attention,
    why: why
  };
});

process.stdout.write(
  JSON.stringify(rendered)
);
'''


TEMP.write_text(
    renderer_script,
    encoding="utf-8"
)


renderer_input = [
    {
        "case_id": source["Case_ID"],
        "prediction": prediction
    }
    for source, prediction, _ in combined
]


proc = subprocess.run(
    ["node", str(TEMP)],
    input=json.dumps(renderer_input),
    text=True,
    capture_output=True,
    cwd=ROOT
)


TEMP.unlink(missing_ok=True)


if proc.returncode != 0:
    raise RuntimeError(
        "Presentation renderer failed:\n"
        + proc.stderr
    )


rendered = {
    row["case_id"]: row
    for row in json.loads(proc.stdout)
}


# ---------------------------------------------------------
# AUDIT VOCABULARY
#
# These are the residential service categories currently
# recognized by presentation.js.
# ---------------------------------------------------------

KNOWN_TRADES = {
    "",
    "NONE",
    "GAS",
    "HVAC",
    "PLUMBING",
    "LOCKSMITH",
    "ELECTRICAL",
    "APPLIANCE",
    "MOISTURE",
    "PEST",
    "PEST_CONTROL",
    "GENERAL",
    "STRUCTURAL",
    "ROOFING",
    "LANDSCAPING",
    "LAWN_CARE",
    "WELDING",
    "TILING",
    "CARPENTRY",
    "PAINTING",
    "MASONRY",
    "HANDYMAN",
    "GARAGE_DOOR",
    "DRAINAGE",
    "FENCING",
    "GLAZING",
    "POOL"
}


# ---------------------------------------------------------
# AUTO-FLAGGING
#
# Flags identify cases worth human review.
# A flag is NOT automatically a product failure.
# ---------------------------------------------------------

def flags_for(source, prediction, human):
    flags = []

    hazards = split_pipe(
        prediction.get(
            "HazardConcepts",
            ""
        )
    )

    meaningful_hazards = [
        hazard
        for hazard in hazards
        if hazard not in {
            "",
            "NONE",
            "NO_HAZARD",
            "NO_ACTIVE_HAZARD"
        }
    ]

    trade = prediction.get(
        "Predicted_PrimaryTrade",
        ""
    ).strip().upper()

    outcome = prediction.get(
        "PolicyOutcome",
        ""
    ).strip().upper()

    information = prediction.get(
        "InformationState",
        ""
    ).strip().upper()

    urgency = prediction.get(
        "Predicted_Urgency",
        ""
    ).strip().upper()

    title = human["title"]
    description = human["description"]
    why = human["why"]

    # Generic presentation deserves review.
    if title == "Maintenance issue":
        flags.append(
            "GENERIC_INTERPRETATION"
        )

    if (
        "structured response does not include"
        in description.lower()
    ):
        flags.append(
            "GENERIC_DESCRIPTION"
        )

    # Unexpected trade vocabulary deserves review.
    if trade not in KNOWN_TRADES:
        flags.append(
            "UNKNOWN_TRADE"
        )

    # Multiple-issue reports deserve a quick human check
    # because the presentation intentionally prioritizes
    # the most important structured concept.
    if prediction.get(
        "MultipleIssues",
        ""
    ).strip().lower() == "true":
        flags.append(
            "MULTI_ISSUE"
        )

    if prediction.get(
        "HazardUnmapped",
        ""
    ).strip().lower() == "true":
        flags.append(
            "UNMAPPED_HAZARD"
        )

    if prediction.get(
        "ConditionUnmapped",
        ""
    ).strip().lower() == "true":
        flags.append(
            "UNMAPPED_CONDITION"
        )

    # A meaningful hazard combined with ACT or CLOSE
    # deserves human inspection. Some security cases can
    # legitimately ACT, so this remains a review flag only.
    if (
        meaningful_hazards
        and outcome in {
            "ACT",
            "CLOSE"
        }
    ):
        flags.append(
            "HAZARD_WITH_LOW_INTERVENTION"
        )

    if (
        urgency in {
            "EMERGENCY",
            "CRITICAL"
        }
        and outcome not in {
            "ACT+ESCALATE",
            "ESCALATE",
            "ACT"
        }
    ):
        flags.append(
            "URGENT_OUTCOME_REVIEW"
        )

    insufficient = information in {
        "INSUFFICIENT",
        "NEEDS_CLARIFICATION",
        "INSUFFICIENT_AFTER_ASK",
        "NO_RESPONSE_AFTER_ASK"
    }

    # ASK/AWAITING normally require an information state
    # that explains why the workflow is waiting.
    if (
        outcome in {
            "ASK",
            "AWAITING"
        }
        and not insufficient
    ):
        flags.append(
            "INFO_STATE_REVIEW"
        )

    # Missing-information language is expected only when
    # the governed outcome still depends on that missing
    # information.
    #
    # ACT and ACT+ESCALATE intentionally suppress this
    # sentence because the next action is already known.
    if (
        insufficient
        and outcome in {
            "ASK",
            "AWAITING",
            "ESCALATE"
        }
        and "more information is needed"
        not in description.lower()
        and "still insufficient"
        not in why.lower()
    ):
        flags.append(
            "MISSING_INFO_EXPLANATION"
        )

    # Machine vocabulary should never leak into the
    # human-facing presentation.
    machine_markers = [
        "P03_",
        "P04_",
        "P15_",
        "NO_ACTIVE_HAZARD",
        "ACTIVE_MAINTENANCE_NEED"
    ]

    visible_text = " ".join([
        title,
        description,
        human["next_action"],
        human["supporting"],
        why
    ])

    if any(
        marker in visible_text
        for marker in machine_markers
    ):
        flags.append(
            "RAW_MACHINE_LANGUAGE"
        )

    # The prototype determines governed next action.
    # It does not claim downstream real-world execution.
    execution_claims = [
        "technician dispatched",
        "tenant contacted",
        "landlord notified",
        "emergency response initiated",
        "repair scheduled",
        "request closed"
    ]

    lower_visible = visible_text.lower()

    if any(
        claim in lower_visible
        for claim in execution_claims
    ):
        flags.append(
            "EXECUTION_CLAIM"
        )

    # Hazard/trade disagreement is not automatically wrong.
    # Hazard-first presentation should normally make these
    # cases understandable, but we still inspect them.
    if (
        "GAS_HAZARD"
        in meaningful_hazards
        and trade not in {
            "",
            "NONE",
            "GAS"
        }
    ):
        flags.append(
            "HAZARD_TRADE_REVIEW"
        )

    if (
        "ELECTRICAL_HAZARD"
        in meaningful_hazards
        and trade not in {
            "",
            "NONE",
            "ELECTRICAL"
        }
    ):
        flags.append(
            "HAZARD_TRADE_REVIEW"
        )

    return flags


# ---------------------------------------------------------
# BUILD AUDIT RECORDS
# ---------------------------------------------------------

records = []


for source, prediction, dataset in combined:
    case_id = source["Case_ID"]
    human = rendered[case_id]

    flags = flags_for(
        source,
        prediction,
        human
    )

    expected = source.get(
        "Expected_Outcome",
        ""
    )

    actual = prediction.get(
        "PolicyOutcome",
        ""
    )

    if expected != actual:
        flags.insert(
            0,
            "OUTCOME_MISMATCH"
        )

    records.append({
        "dataset": dataset,
        "case_id": case_id,

        "request":
            source.get(
                "Request",
                ""
            ),

        "clarification":
            source.get(
                "Clarification_Response",
                ""
            ),

        "expected":
            expected,

        "outcome":
            actual,

        "rule":
            prediction.get(
                "PolicyRule",
                ""
            ),

        "hazards":
            prediction.get(
                "HazardConcepts",
                ""
            ),

        "conditions":
            prediction.get(
                "ConditionConcepts",
                ""
            ),

        "information":
            prediction.get(
                "InformationState",
                ""
            ),

        "urgency":
            prediction.get(
                "Predicted_Urgency",
                ""
            ),

        "trade":
            prediction.get(
                "Predicted_PrimaryTrade",
                ""
            ),

        "multiple":
            prediction.get(
                "MultipleIssues",
                ""
            ),

        "title":
            human["title"],

        "description":
            human["description"],

        "next_action":
            human["next_action"],

        "supporting":
            human["supporting"],

        "why":
            human["why"],

        "flags":
            flags
    })


# ---------------------------------------------------------
# SUMMARY METRICS
# ---------------------------------------------------------

flagged_count = sum(
    bool(record["flags"])
    for record in records
)


outcome_mismatches = sum(
    "OUTCOME_MISMATCH"
    in record["flags"]
    for record in records
)


flag_counts = Counter(
    flag
    for record in records
    for flag in record["flags"]
)


# ---------------------------------------------------------
# HTML HELPERS
# ---------------------------------------------------------

def esc(value):
    return html.escape(
        str(value or "")
    )


def flag_html(flags):
    if not flags:
        return (
            '<span class="ok">'
            'NO AUTO-FLAGS'
            '</span>'
        )

    return " ".join(
        (
            f'<span class="flag">'
            f'{esc(flag)}'
            f'</span>'
        )
        for flag in flags
    )


def clarification_html(value):
    value = str(
        value or ""
    ).strip()

    if not value:
        return ""

    return f"""
      <section class="clarification">
        <div class="label">
          CLARIFICATION RESPONSE
        </div>

        <div class="clarification-text">
          {esc(value)}
        </div>
      </section>
    """


# ---------------------------------------------------------
# BUILD CASE CARDS
# ---------------------------------------------------------

cards = []


for record in records:
    card_class = (
        "case flagged"
        if record["flags"]
        else "case"
    )

    clarification = clarification_html(
        record["clarification"]
    )

    cards.append(f"""
    <article class="{card_class}">

      <div class="case-head">
        <div>
          <span class="dataset">
            {esc(record['dataset'])}
          </span>

          <strong>
            {esc(record['case_id'])}
          </strong>
        </div>

        <div>
          {flag_html(record['flags'])}
        </div>
      </div>

      <section>
        <div class="label">
          ORIGINAL REPORT
        </div>

        <div class="report">
          {esc(record['request'])}
        </div>
      </section>

      {clarification}

      <div class="grid">

        <section>
          <div class="label">
            STRUCTURED INTERPRETATION
          </div>

          <dl>
            <dt>Hazard</dt>
            <dd>
              {esc(record['hazards'])}
            </dd>

            <dt>Condition</dt>
            <dd>
              {esc(record['conditions'])}
            </dd>

            <dt>Urgency</dt>
            <dd>
              {esc(record['urgency'])}
            </dd>

            <dt>Trade</dt>
            <dd>
              {esc(record['trade'])}
            </dd>

            <dt>Information</dt>
            <dd>
              {esc(record['information'])}
            </dd>

            <dt>Multiple issues</dt>
            <dd>
              {esc(record['multiple'])}
            </dd>
          </dl>
        </section>

        <section>
          <div class="label">
            WHAT USER SEES
          </div>

          <h2>
            {esc(record['title'])}
          </h2>

          <p>
            {esc(record['description'])}
          </p>

          <div class="next">
            <div class="label">
              WHAT HAPPENS NEXT
            </div>

            <h3>
              {esc(record['next_action'])}
            </h3>

            <strong>
              {esc(record['supporting'])}
            </strong>
          </div>

          <div class="why">
            <div class="label">
              WHY
            </div>

            {esc(record['why'])}
          </div>
        </section>

      </div>

      <section class="policy">
        Expected:
        <strong>
          {esc(record['expected'])}
        </strong>

        &nbsp; · &nbsp;

        Actual:
        <strong>
          {esc(record['outcome'])}
        </strong>

        &nbsp; · &nbsp;

        Rule:
        {esc(record['rule'])}
      </section>

    </article>
    """)


flag_summary_html = "".join(
    f"""
      <span class="flag-summary">
        {esc(name)}: {count}
      </span>
    """
    for name, count
    in flag_counts.most_common()
)


# ---------------------------------------------------------
# BUILD HTML DOCUMENT
# ---------------------------------------------------------

document = f"""<!doctype html>

<html lang="en">

<head>

<meta charset="utf-8">

<meta
  name="viewport"
  content="width=device-width, initial-scale=1"
>

<title>
  Maintenance Autopilot — 111 Output Quality Audit
</title>

<style>

  * {{
    box-sizing: border-box;
  }}

  body {{
    margin: 0;

    font-family:
      Inter,
      system-ui,
      -apple-system,
      BlinkMacSystemFont,
      "Segoe UI",
      sans-serif;

    background: #f5f7f5;
    color: #102d24;
  }}

  header {{
    position: sticky;
    top: 0;
    z-index: 10;

    padding: 20px 28px;

    background: #ffffff;

    border-bottom:
      1px solid #dbe4df;
  }}

  header h1 {{
    margin: 0 0 8px;
    font-size: 24px;
  }}

  header p {{
    margin: 0;
    color: #53675f;
  }}

  .summary {{
    display: flex;
    flex-wrap: wrap;

    gap: 24px;

    margin-top: 12px;

    font-weight: 700;
  }}

  .flag-summary-row {{
    display: flex;
    flex-wrap: wrap;

    gap: 7px;

    margin-top: 12px;
  }}

  .flag-summary {{
    padding: 4px 8px;

    border-radius: 6px;

    background: #fff1d6;
    color: #855500;

    font-size: 11px;
    font-weight: 700;
  }}

  main {{
    max-width: 1400px;

    margin: 0 auto;
    padding: 24px;
  }}

  .case {{
    margin-bottom: 18px;
    padding: 22px;

    background: #ffffff;

    border:
      1px solid #dce5e0;

    border-radius: 14px;

    box-shadow:
      0 4px 18px
      rgba(0, 0, 0, .03);
  }}

  .case.flagged {{
    border-left:
      5px solid #c98b20;
  }}

  .case-head {{
    display: flex;

    justify-content:
      space-between;

    align-items:
      flex-start;

    gap: 20px;

    margin-bottom: 20px;
  }}

  .dataset {{
    display: inline-block;

    margin-right: 8px;

    padding: 4px 7px;

    background: #e7f3ee;
    color: #087758;

    border-radius: 6px;

    font-size: 11px;
    font-weight: 800;
  }}

  .label {{
    margin-bottom: 7px;

    color: #60756c;

    font-size: 11px;
    font-weight: 800;

    letter-spacing: .08em;
  }}

  .report {{
    padding: 14px;

    background: #f8faf9;

    border-radius: 8px;

    font-size: 17px;
    line-height: 1.5;
  }}

  .clarification {{
    margin-top: 12px;
  }}

  .clarification-text {{
    padding: 12px 14px;

    background: #fff8e8;

    border-left:
      4px solid #d59a2a;

    border-radius: 6px;

    font-size: 15px;
    line-height: 1.5;
  }}

  .grid {{
    display: grid;

    grid-template-columns:
      1fr 1.4fr;

    gap: 28px;

    margin-top: 22px;
  }}

  dl {{
    display: grid;

    grid-template-columns:
      120px 1fr;

    gap: 7px 12px;

    margin: 0;
  }}

  dt {{
    color: #657970;
  }}

  dd {{
    margin: 0;

    font-weight: 600;

    word-break: break-word;
  }}

  h2 {{
    margin: 0 0 8px;

    font-size: 24px;
  }}

  h3 {{
    margin: 5px 0 7px;

    font-size: 26px;
  }}

  p {{
    line-height: 1.5;
  }}

  .next {{
    margin-top: 18px;
    padding-top: 18px;

    border-top:
      1px solid #dce5e0;
  }}

  .why {{
    margin-top: 18px;
    padding: 14px 16px;

    background: #e9f5f0;

    border-left:
      4px solid #087758;
  }}

  .policy {{
    margin-top: 20px;
    padding-top: 14px;

    border-top:
      1px solid #dce5e0;

    color: #566b62;

    font-size: 13px;
  }}

  .flag {{
    display: inline-block;

    margin:
      0 3px 4px 0;

    padding: 4px 7px;

    background: #fff1d6;
    color: #855500;

    border-radius: 6px;

    font-size: 10px;
    font-weight: 800;
  }}

  .ok {{
    color: #087758;

    font-size: 11px;
    font-weight: 800;
  }}

  @media (max-width: 800px) {{

    .grid {{
      grid-template-columns: 1fr;
    }}

    .case-head {{
      display: block;
    }}

  }}

</style>

</head>

<body>

<header>

  <h1>
    Maintenance Autopilot —
    111 Output Quality Audit
  </h1>

  <p>
    Original report →
    clarification →
    structured interpretation →
    exact current human presentation.
  </p>

  <div class="summary">

    <span>
      111 cases
    </span>

    <span>
      {flagged_count}
      auto-flagged for review
    </span>

    <span>
      {outcome_mismatches}
      outcome mismatches
    </span>

  </div>

  <div class="flag-summary-row">
    {flag_summary_html}
  </div>

</header>

<main>

  {''.join(cards)}

</main>

</body>

</html>
"""


# ---------------------------------------------------------
# WRITE REPORT
# ---------------------------------------------------------

OUT.write_text(
    document,
    encoding="utf-8"
)


# ---------------------------------------------------------
# TERMINAL SUMMARY
# ---------------------------------------------------------

print()

print(
    "111-case output audit complete"
)

print(
    "--------------------------------"
)

print(
    f"Cases:              "
    f"{len(records)}"
)

print(
    f"Auto-flagged:       "
    f"{flagged_count}"
)

print(
    f"Outcome mismatches: "
    f"{outcome_mismatches}"
)

print()


if flag_counts:
    print(
        "Auto-flag summary:"
    )

    for name, count in (
        flag_counts.most_common()
    ):
        print(
            f"  {name:<30} "
            f"{count}"
        )

else:
    print(
        "Auto-flag summary: none"
    )


print()

print(
    f"Report: {OUT}"
)