\# Evaluation



Maintenance Autopilot is evaluated as a bounded-autonomy system.



The primary question is not whether every intermediate AI classification is

perfect. It is whether the complete system makes the correct next-action

decision, preserves critical escalation boundaries, and avoids unsafe

autonomous action.



The evaluation therefore separates:



1\. semantic interpretation,

2\. deterministic policy,

3\. the human/autonomy boundary, and

4\. end-to-end decision performance.



\---



\## Evaluation Metrics



\### Policy Outcome Accuracy



Percentage of cases where the final system outcome matches the expected

outcome.



Controlled outcomes are:



\- `ACT`

\- `ASK`

\- `AWAITING`

\- `ESCALATE`

\- `ACT+ESCALATE`

\- `CLOSE`



\### Critical Escalation Recall



A case is counted as critical when ground truth marks it as `Unsafe` and the

expected outcome contains `ESCALATE`.



Critical escalation recall measures how often the system preserves that

required escalation.



\### Unsafe Autonomous Actions



An unsafe autonomous action occurs when a critical case that requires

escalation instead receives a final outcome of `ACT`.



This is deliberately narrower than general outcome error.



\---



\# Evaluation History



\## Original Sealed Holdout



The first architecture was tested against a sealed 24-case holdout.



It did not perform well enough.



| Metric | Raw Agent | Governed |

|---|---:|---:|

| Outcome accuracy | 50.0% | 62.5% |

| Critical escalation recall | 0.0% | 33.3% |

| Unsafe autonomous actions | 3 | 2 |



The deterministic governor improved the result, but two unsafe autonomous

actions remained.



This failure was treated as an architecture problem rather than a prompt

tuning problem.



It led to the V2 redesign: semantic interpretation was separated from

deterministic authority.



\---



\# V2.5 Architecture Evaluation



V2.5 uses Strands Agents and Amazon Bedrock to interpret the maintenance

request, while deterministic policy controls the final authority decision.



Two development evaluation sets are retained in the repository.



\## 61-Case Regression Set



| Metric | V2.5 |

|---|---:|

| Policy outcome accuracy | \*\*100.0% (61/61)\*\* |

| Critical escalation recall | \*\*100.0% (11/11)\*\* |

| Unsafe autonomous actions | \*\*0\*\* |

| Safety classification accuracy | 80.3% |

| Urgency classification accuracy | 75.4% |

| Primary trade accuracy | 92.7% |



\## 50-Case Challenge / Regression Set



| Metric | V2.5 |

|---|---:|

| Policy outcome accuracy | \*\*100.0% (50/50)\*\* |

| Critical escalation recall | \*\*100.0% (12/12)\*\* |

| Unsafe autonomous actions | \*\*0\*\* |

| Safety classification accuracy | 72.0% |

| Urgency classification accuracy | 68.0% |

| Primary trade accuracy | 70.2% |



These are regression results, not a claim of general real-world accuracy.



The 50-case challenge set was used during V2.x development and therefore is

not treated as an independent holdout.



\---



\# Semantic Errors and Decision Errors Are Not the Same



An important result appears when intermediate semantic classifications are

compared with final policy outcomes.



\### 61-case regression set



\- Exact on all scored semantic dimensions: \*\*34/61 (55.7%)\*\*

\- At least one semantic mismatch: \*\*27/61 (44.3%)\*\*

\- Correct final outcome despite semantic mismatch: \*\*27/27\*\*



\### 50-case challenge / regression set



\- Exact on all scored semantic dimensions: \*\*18/50 (36.0%)\*\*

\- At least one semantic mismatch: \*\*32/50 (64.0%)\*\*

\- Correct final outcome despite semantic mismatch: \*\*32/32\*\*



This does not mean deterministic policy "corrected" every semantic error.



Some intermediate classification mismatches are not decision-changing.



The result instead demonstrates an important property of the architecture:

intermediate semantic exact-match errors did not necessarily propagate into

final decision errors.



The system is evaluated primarily on whether the correct authority boundary

is preserved.



\---



\# Human / Autonomy Boundary



Maintenance Autopilot does not attempt to maximize autonomous action.



Its controlled outcomes deliberately preserve different forms of human

involvement.



\## 61-case regression set



| Decision Boundary | Cases | Share |

|---|---:|---:|

| Autonomous progression (`ACT` / `CLOSE`) | 31 | 50.8% |

| Information / dependency (`ASK` / `AWAITING`) | 4 | 6.6% |

| Human judgment (`ESCALATE`) | 13 | 21.3% |

| Protective action + human judgment (`ACT+ESCALATE`) | 13 | 21.3% |



\## 50-case challenge / regression set



| Decision Boundary | Cases | Share |

|---|---:|---:|

| Autonomous progression (`ACT` / `CLOSE`) | 26 | 52.0% |

| Information / dependency (`ASK` / `AWAITING`) | 3 | 6.0% |

| Human judgment (`ESCALATE`) | 7 | 14.0% |

| Protective action + human judgment (`ACT+ESCALATE`) | 14 | 28.0% |



Across both representative development sets, roughly half of cases progressed

autonomously.



The remainder deliberately retained an information, safety, or judgment

boundary.



Correct escalation is therefore considered successful agent behavior, not

agent failure.



\---



\# Contribution Analysis: Why Use a Semantic Agent?



A deterministic policy can enforce an authority boundary only when the system

first recognizes enough meaning in the maintenance report to invoke the

correct rule.



To test the contribution of semantic interpretation, V2.5 was compared

retrospectively with a deliberately simple lexical baseline.



\## Baseline Design



The baseline replaces the Strands / Bedrock semantic interpretation with

simple phrase and keyword matching.



It retains the same deterministic policy engine.



The baseline does not use:



\- Strands Agents,

\- Amazon Bedrock,

\- semantic similarity,

\- fuzzy matching, or

\- case-specific exception rules.



The lexical baseline was committed and frozen before its evaluation score was

observed.



This is an architecture ablation, not a comparison against another production

system.



\---



\## Ablation Results



| Evaluation | Metric | Lexical + Policy | Strands/Bedrock + Policy |

|---|---|---:|---:|

| 61 cases | Outcome accuracy | 77.0% | \*\*100.0%\*\* |

| 61 cases | Critical escalation recall | 54.5% | \*\*100.0%\*\* |

| 61 cases | Unsafe autonomous actions | 5 | \*\*0\*\* |

| 50 cases | Outcome accuracy | 62.0% | \*\*100.0%\*\* |

| 50 cases | Critical escalation recall | 25.0% | \*\*100.0%\*\* |

| 50 cases | Unsafe autonomous actions | 8 | \*\*0\*\* |



The lexical baseline also crossed a broader human/information boundary into

`ACT` in 8 of 61 cases and 13 of 50 cases.



Most importantly, all 13 formally unsafe autonomous actions across the two

sets fell through to:



`P15\_ROUTINE\_AUTHORIZED\_ACTION`



The deterministic policy therefore did what it was designed to do with the

facts it received. The failure occurred earlier: the lexical interpretation

did not recognize enough context to activate the required safety boundary.



The comparison supports the hybrid design:



\*\*AI interprets. Policy bounds. Humans judge.\*\*



Semantic interpretation provides contextual understanding of messy

real-world maintenance language.



Deterministic policy controls what authority follows from that

interpretation.



Human judgment remains explicit where the policy boundary says autonomy

should stop.



\---



\# What This Evaluation Does Not Prove



These results should not be interpreted as:



\- 100% real-world accuracy,

\- proof that every semantic classification is correct,

\- proof that all maintenance domains are covered,

\- proof that the prototype is production-ready, or

\- proof that Strands / Bedrock alone produces the final decisions.



The 61-case and 50-case sets were used during system development.



The lexical comparison is therefore a retrospective contribution analysis,

not independent generalization evidence.



The system's intended scope is defined separately in

\[`OPERATING\_ENVELOPE.md`](OPERATING\_ENVELOPE.md).



\---



\# Generalization Test



A separate sealed evaluation set, Holdout C, is reserved for the frozen

system.



The sequence is intentionally:



1\. freeze the operating envelope,

2\. freeze the V2.5 architecture,

3\. design Holdout C within that envelope,

4\. seal expected outcomes,

5\. run the frozen deployed system once, and

6\. publish the result unchanged.



No tuning will be performed against Holdout C after its results are observed.



This separates regression evidence from a genuine test of unseen cases.



\---



\# Reproducing the Analysis



The standard evaluator is:



```bash

python evaluation/evaluate\_v2.py \\

&#x20; --truth <ground-truth.csv> \\

&#x20; --predictions <predictions.csv>

