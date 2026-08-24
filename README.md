# Maintenance Autopilot

**An AI maintenance-triage agent built for the AWS Agents for Humans hackathon using the Strands Agents SDK and Amazon Bedrock.**

Maintenance Autopilot interprets rental-maintenance reports and routes them through a controlled decision policy:

`ACT` · `ASK` · `AWAITING` · `ESCALATE` · `ACT+ESCALATE` · `CLOSE`

> This is a personal hackathon project built with synthetic rental-maintenance scenarios. It is separate from employer systems, data, and intellectual property.

## Why this exists

A small landlord may receive dozens of maintenance messages each month, but most do not require personal judgment. Some should proceed routinely, some need clarification, some should wait, and some require immediate protective action or owner involvement.

The core design principle is:

> **Use AI to interpret what is happening. Use deterministic policy to control what must happen next.**

## Architecture

```text
Tenant maintenance report
            |
            v
 Cross-symptom hazard check
            |
            v
      Issue decomposition
            |
       +----+----+
       |         |
       v         v
    Hazard      Case
   Assessor   Assessor
       |         |
       +----+----+
            |
            v
    Validated concepts
            |
            v
   Deterministic policy
            |
            v
 ACT / ASK / AWAITING /
 ESCALATE / ACT+ESCALATE
```

Core components:
- **Strands Agents SDK** — semantic agent components
- **Amazon Bedrock** — model layer
- **Hazard Assessor** — safety/security hazard concepts
- **Case Assessor** — condition, information sufficiency, urgency, trade
- **Repeat Failure Assessor** — recurrence comparison
- **Deterministic Policy Engine** — final controlled outcome
- **Fail-safe handling** — unmapped concepts do not silently pass as routine work

![Maintenance Autopilot V2.5 architecture](docs/architecture.png)

## Evaluation journey

### Original sealed holdout — 24 scenarios

| Metric | Raw agent | Governed system |
|---|---:|---:|
| Outcome accuracy | 50.0% | 62.5% |
| Critical escalation recall | 0.0% | 33.3% |
| Unsafe autonomous actions | 3 | 2 |

The governor corrected 5 decisions but introduced 2 regressions. That sealed test triggered the V2 redesign.

### Frozen V2.5

| Evaluation set | Cases | Policy outcome accuracy | Critical escalation recall | Unsafe autonomous actions |
|---|---:|---:|---:|---:|
| Regression benchmark | 61 | 100.0% | 100.0% | 0 |
| Challenge/regression set | 50 | 100.0% | 100.0% | 0 |

**Qualification:** the 50-case challenge set was used during V2.x improvement, so it is not presented as a pristine final holdout.

## Repository structure

```text
maintenance-autopilot/
├── app/
│   ├── __init__.py
│   ├── tools.py
│   ├── v2_agent.py
│   ├── v2_case.py
│   ├── v2_case_validator.py
│   ├── v2_decompose.py
│   ├── v2_hazard.py
│   ├── v2_hazard_validator.py
│   ├── v2_policy.py
│   └── v2_repeat.py
├── data/
│   └── sample_cases.csv
├── evaluation/
│   └── evaluate_v2.py
├── docs/
│   ├── architecture.png
│   └── TESTING.md
├── README.md
├── RELEASE.md
├── LICENSE
├── requirements.txt
└── .gitignore
```

Do **not** publish `.venv`, AWS credentials, cache files, private notes, or failed/backup variants.

## Quick start

### Prerequisites
- Python 3.10+
- AWS account with access to the Amazon Bedrock model used by the project
- AWS credentials configured locally
- Git

### Clone

```bash
git clone https://github.com/Anthony-hue25/maintenance-autopilot.git
cd maintenance-autopilot
```

### Create environment

Windows PowerShell:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install

```bash
pip install -r requirements.txt
```

### Configure AWS

This repository contains **no AWS credentials**.

```bash
aws sts get-caller-identity
```

If your environment uses AWS login sessions:

```bash
aws login
```

### Run sample

Windows PowerShell:

```powershell
python -u -m app.v2_agent --input data\sample_cases.csv --output data\sample_predictions.csv
```

macOS/Linux:

```bash
python -u -m app.v2_agent --input data/sample_cases.csv --output data/sample_predictions.csv
```

## Judge testing

See `docs/TESTING.md`.

A hosted judge demo will be added separately so judges do not depend on the author's local AWS session.

## Safety design

The model does not freely invent final actions. Semantic assessors produce structured concepts; deterministic policy selects the final workflow outcome.

Examples:
- critical hazards can require `ACT+ESCALATE`
- missing decision-changing information can require `ASK`
- non-safety silence after clarification can become `AWAITING`
- repeat failures can require `ESCALATE`
- routine authorized maintenance can proceed as `ACT`
- unmapped concepts fail conservatively

This is a **validated prototype**, not production property-management software.

## Build journey

AWS Builder Center article:

**Agents for Humans: Building a Maintenance Agent That Knows When Not to Act**

https://builder.aws.com/content/3IKuc6YmvnqxJjy3OpIV89JOTSd/agents-for-humans-building-a-maintenance-agent-that-knows-when-not-to-act

## License

MIT. See `LICENSE`.
