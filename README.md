# Maintenance Autopilot

**A bounded-autonomy maintenance agent that knows when to act — and when not to.**

Built for the AWS **Agents for Humans** hackathon using the **Strands Agents SDK**, **Amazon Bedrock**, and **Amazon Bedrock AgentCore**.

[Live Demo](https://sproductiontaging.d5cp73uy4chyq.amplifyapp.com) · [Build Story](https://builder.aws.com/content/3IKuc6YmvnqxJjy3OpIV89JOTSd/agents-for-humans-building-a-maintenance-agent-that-knows-when-not-to-act)

> Personal hackathon project using synthetic residential-maintenance scenarios. It is separate from employer systems, data, and intellectual property.

---

## The problem

A small landlord can receive many maintenance reports, but not every report needs the same level of human attention.

A dripping faucet may be routine. A vague security issue may need clarification. A repair above the owner's authority limit needs approval. A gas hazard needs protective action and human escalation.

The challenge is therefore not simply:

> Can an AI agent act?

It is also:

> **Does it know when it should not act on its own?**

Maintenance Autopilot explores that boundary.

---

## The design principle

> **Use AI to interpret what is happening. Use deterministic policy to control what must happen next.**

The language model does not have unrestricted authority to choose the final workflow action.

Instead, AI components interpret an unstructured maintenance report into structured, decision-relevant concepts. A deterministic policy engine then applies explicit authority and safety rules.

The six governed outcomes are:

`ACT` · `ASK` · `AWAITING` · `ESCALATE` · `ACT+ESCALATE` · `CLOSE`

Examples:

- `ACT` — routine authorized work can progress
- `ASK` — decision-changing information is missing
- `AWAITING` — a non-safety clarification was requested but no response was received
- `ESCALATE` — the issue exceeds an authority or decision boundary
- `ACT+ESCALATE` — protective action is required while returning the decision to a human
- `CLOSE` — no maintenance action remains

---

## Try the live system

**[Open Maintenance Autopilot](https://sproductiontaging.d5cp73uy4chyq.amplifyapp.com)**

The judge-facing demo accepts a maintenance report in natural language and returns:

1. what Autopilot understood
2. what should happen next
3. why
4. the technical decision trace

Four examples are included in the interface to demonstrate different authority boundaries:

- routine dripping faucet
- window that will not latch
- AC repair quoted above authority
- escalating gas smell

The live response is produced through the deployed AWS system — it is not a prerecorded or hard-coded decision.

---

## How it works

```text
Maintenance report
        |
        v
+-----------------------+
| AI interpretation     |
|                       |
| Issue decomposition   |
| Hazard assessment     |
| Case assessment       |
| Repeat assessment     |
+-----------+-----------+
            |
            v
+-----------------------+
| Validated concepts    |
|                       |
| hazard                |
| condition             |
| information state     |
| urgency               |
| trade                 |
| repeat signal         |
+-----------+-----------+
            |
            v
+-----------------------+
| Deterministic policy  |
|                       |
| safety boundaries     |
| authority limits      |
| clarification rules   |
| escalation rules      |
+-----------+-----------+
            |
            v
 ACT / ASK / AWAITING / ESCALATE
      / ACT+ESCALATE / CLOSE
```

This separation is deliberate:

**AI interprets the situation. Policy controls the authority.**

---

## AWS deployment

The public demo follows this path:

```text
Browser
  |
  v
AWS Amplify
  |
  v
Amazon API Gateway
  |
  v
AWS Lambda
  |
  v
Amazon Bedrock AgentCore
  |
  v
Strands-based V2.5 agent
  |
  v
Amazon Bedrock
```

The browser does not invoke AgentCore directly.

The server-side API validates the public request, injects controlled property context, invokes the AgentCore runtime, validates the returned decision contract, and sends a normalized result to the frontend.

### Main technologies

- **Strands Agents SDK** — semantic agent components
- **Amazon Bedrock** — model inference
- **Amazon Bedrock AgentCore** — deployed agent runtime
- **AWS Lambda** — public API adapter
- **Amazon API Gateway** — controlled HTTP boundary
- **AWS Amplify** — static judge-facing application
- **CloudWatch** — runtime observability
- **Python** — agent, policy, evaluation, and API logic
- **HTML/CSS/JavaScript** — lightweight public interface

![Maintenance Autopilot V2.5 architecture](docs/architecture.png)

---

## Evaluation

Maintenance Autopilot was tested at three different levels.

| Evaluation | What it tests | Result |
|---|---|---:|
| Development evaluation | Policy correctness during V2.5 development | **111/111** governed outcomes correct |
| Deployed hardening | Stability of four frozen showcase cases against deployed AgentCore | **40/40** passed |
| Post-freeze Holdout C | Generalization after the application and expected answers were locked | **63/80 (78.8%)** |

These results are deliberately reported separately because they answer different questions.

### Post-freeze Holdout C

The final 80-case holdout dataset and expected outcomes were locked after the application was frozen and before the official evaluation was executed.

Expected governed outcomes were locked before execution. The official evaluation was then completed once, with no post-result tuning or selective reruns.

| Expected outcome | Correct |
|---|---:|
| `ACT+ESCALATE` | **15/15 (100%)** |
| `AWAITING` | **8/8 (100%)** |
| `CLOSE` | **10/10 (100%)** |
| `ACT` | **17/18 (94.4%)** |
| `ASK` | **5/11 (45.5%)** |
| `ESCALATE` | **8/18 (44.4%)** |
| **Overall** | **63/80 (78.8%)** |

The strongest result is directly related to the project's safety objective:

> **All 15/15 holdout cases requiring protective `ACT+ESCALATE` behavior were correctly governed.**

The holdout also exposed a real limitation. Performance was weaker at clarification and non-critical escalation boundaries, particularly where the semantic interpretation layer needed to identify repeat failure, progression, or insufficient information.

Those misses were retained. The application was not tuned or rerun to improve the Holdout C score.

### Reproducibility trail

The evaluation sequence is preserved in Git:

```text
b5d9f88
submission-freeze-2026-09-06
Application frozen
        |
        v
71e92bb
holdout-c-preregistered-2026-09-06
80-case ground truth locked
        |
        v
One official execution
        |
        v
ae3b88c
holdout-c-results-2026-09-06
Predictions and results preserved
```

The ground-truth and official-prediction SHA-256 hashes are recorded with the Holdout C evidence in `data/holdout_c_results.txt`.

---

## What the holdout taught me

The result highlights an important distinction in governed-agent design.

The deterministic policy can correctly enforce a boundary **only when the semantic layer successfully surfaces the decision-critical fact needed by that rule**.

Several Holdout C misses occurred because repeat, progression, or information-sufficiency signals were not recognized strongly enough by the interpretation layer. The deterministic governor then applied the rule corresponding to the facts it actually received.

That suggests a clear next engineering direction: improve semantic extraction and validation without weakening the deterministic authority boundary.

---

## Safety and authority design

The final action is not freely generated by the language model.

Examples of explicit policy behavior include:

- critical hazards require protective action plus human escalation
- primary-entrance security exposure requires protective action plus escalation
- repair cost above configured authority requires escalation
- missing decision-changing information can require clarification
- non-safety silence after a clarification request can wait
- repeat failures can require escalation
- replacement or upgrade recommendations require escalation
- property damage can require action plus escalation
- resolved cases close
- unmapped decision-critical concepts fail conservatively

The public API adds another boundary around the agent:

- strict request schema
- server-controlled property context
- input length limits
- restrictive CORS
- API throttling
- bounded retry for transient AgentCore failure
- response-contract validation
- no raw backend errors returned to the browser
- no claim that a technician was actually dispatched or repair executed

This remains a **prototype**, not production property-management or emergency-response software.

---

## Repository guide

Key areas of the repository:

```text
app/
  V2.5 semantic assessors and deterministic policy

MaintAutopilot/
  AgentCore runtime and deployment implementation

infrastructure/
  Public AWS API infrastructure

web/
  Judge-facing application and presentation layer

data/
  Development datasets, Holdout C ground truth,
  official predictions and preserved results

hardening_results/
  Repeated deployed showcase evaluation evidence

frozen/v2_5/
  Frozen V2.5 reference implementation

docs/
  Architecture and testing documentation
```

Important evaluation artifacts include:

- `data/holdout_c_ground_truth.csv`
- `data/holdout_c_predictions_official.csv`
- `data/holdout_c_results.txt`
- deployed hardening results under `hardening_results/`

---

## Run locally

### Prerequisites

- Python 3.10+
- AWS account with access to the required Amazon Bedrock model
- AWS authentication configured locally
- Git

Clone:

```bash
git clone https://github.com/Anthony-hue25/maintenance-autopilot.git
cd maintenance-autopilot
```

Create a virtual environment on Windows PowerShell:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Verify AWS authentication:

```powershell
aws sts get-caller-identity
```

Run the sample cases:

```powershell
python -u -m app.v2_agent `
  --input .\data\sample_cases.csv `
  --output .\data\sample_predictions.csv
```

See `docs/TESTING.md` for additional evaluation guidance.

---

## Build story

The project evolved through failure rather than beginning with the final architecture.

An earlier sealed evaluation showed that adding a simple governor around an AI agent was not enough. That failure drove the redesign toward explicit semantic concepts, validation, deterministic policy, fail-safe behavior, and eventually the deployed V2.5 architecture.

I documented that journey here:

**[Agents for Humans: Building a Maintenance Agent That Knows When Not to Act](https://builder.aws.com/content/3IKuc6YmvnqxJjy3OpIV89JOTSd/agents-for-humans-building-a-maintenance-agent-that-knows-when-not-to-act)**

---

## Scope

Maintenance Autopilot currently demonstrates governed decision-making for synthetic residential-maintenance scenarios.

It does **not** currently provide:

- contractor dispatch
- work-order execution
- payments
- tenant identity/authentication
- production property-system integration
- emergency-service integration

Those would require additional operational, security, privacy, and human-control design before production use.

---

## License

MIT. See `LICENSE`.