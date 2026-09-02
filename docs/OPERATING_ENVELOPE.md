\# Maintenance Autopilot V2.5 — Operating Envelope



Maintenance Autopilot V2.5 is a prototype for bounded-autonomy maintenance triage in ordinary residential rental properties.



Its purpose is to interpret a natural-language maintenance report and determine the appropriate next action within predefined safety, information, urgency, trade and authority boundaries.



It is not intended to provide complete physical diagnosis, engineering design, repair instructions, legal advice, insurance decisions, or unrestricted autonomous action.



\## Core Design Principle



Maintenance Autopilot separates three responsibilities:



\*\*Strands + Amazon Bedrock — Understand\*\*  

Interpret messy natural-language maintenance reports and identify the relevant maintenance concepts.



\*\*Deterministic Policy — Bound Authority\*\*  

Apply explicit rules governing what the system may do, what information is required, and when autonomous action must stop.



\*\*Human — Retain Judgment\*\*  

Take over when the decision falls outside the system's defined authority, requires material judgment, or cannot be resolved safely within the available information.



The objective is not maximum autonomy. The objective is useful autonomy within clear boundaries.



\## In-Scope Environment



The operating environment is an ordinary residential rental property.



Representative issues include:



\- plumbing leaks, blockages and fixture failures

\- electrical symptoms and minor electrical faults

\- doors, windows, locks and security hardware

\- HVAC and comfort-related equipment

\- appliances and ordinary household fixtures

\- smoke alarms and similar residential safety devices

\- moisture, water ingress and minor building-fabric concerns

\- routine general maintenance defects



The system is designed for maintenance triage and next-action decisions rather than specialist technical diagnosis.



\## Input



The primary input is a natural-language maintenance report from a tenant, property manager, owner, or similar user.



The report may be incomplete, informal, ambiguous, contain multiple symptoms, or use non-technical language.



The system does not currently rely on:



\- photographs or video

\- sensor feeds

\- formal inspection reports

\- drawings

\- diagnostic test data

\- direct equipment telemetry



\## Decision Scope



Maintenance Autopilot determines the appropriate next-action state.



The controlled outcomes are:



\- \*\*ACT\*\* — proceed with a bounded routine action within defined authority

\- \*\*ASK\*\* — request one decision-changing piece of information

\- \*\*AWAITING\*\* — wait for a required response or dependency

\- \*\*ESCALATE\*\* — return the decision to a human

\- \*\*ACT+ESCALATE\*\* — take a protective bounded action while simultaneously escalating

\- \*\*CLOSE\*\* — no further maintenance action is required



These outcomes are intentionally constrained.



The system does not generate unrestricted autonomous actions.



\## Information Boundary



The system follows the principle:



> Ask only for decision-changing information.



Where clarification is needed, the prototype permits one ASK round.



If sufficient information still cannot be obtained, or the unresolved uncertainty affects safety or authority, the system does not continue an open-ended diagnostic conversation.



It moves to the appropriate awaiting, protective or human-escalation state.



\## Safety and Security Boundary



The system is expected to recognize credible safety or security indicators and apply protective or escalation policy.



Examples include conditions involving:



\- possible electrical danger

\- active fire or smoke concerns

\- significant water interaction with electrical equipment

\- inability to secure a primary entrance

\- other immediate residential safety or security concerns



Where a bounded protective action is permitted, the system may select \*\*ACT+ESCALATE\*\*.



The system is not intended to provide definitive hazard clearance, certify that an environment is safe, or replace emergency services or appropriately qualified professionals.



\## Authority Boundary



Routine maintenance may progress autonomously only where it is inside the defined prototype authority.



The current autonomous spending authority is:



\*\*Up to and including $200.\*\*



Work above this boundary requires human escalation unless another explicit protective policy applies.



This prototype does not have authority for:



\- unrestricted purchasing

\- open-ended contractor commitments

\- long-term commercial agreements

\- insurance decisions

\- legal decisions

\- tenancy enforcement

\- major capital expenditure



\## Human Judgment Boundary



Human involvement is an intentional part of the architecture, not simply a fallback for model failure.



The system should return a decision to a human when:



\- authority is exceeded

\- meaningful safety uncertainty remains

\- a decision requires owner or property-manager judgment

\- information cannot be resolved within the permitted clarification boundary

\- the issue materially exceeds ordinary residential maintenance triage

\- policy explicitly requires escalation



A correct escalation is considered successful system behaviour.



\## Out of Scope



The current operating envelope does not claim reliable handling of specialist or materially different environments such as:



\- industrial or commercial facilities

\- elevators or lift systems

\- swimming pools and specialist pool equipment

\- asbestos or hazardous-material assessment

\- major structural engineering problems

\- complex fire-protection systems

\- specialist building-management systems

\- high-voltage electrical systems

\- major civil or geotechnical issues

\- specialist medical, laboratory or regulated infrastructure



The prototype may recognize that an issue appears outside its intended boundary, but it does not claim specialist diagnosis or autonomous resolution of these cases.



\## Evaluation Boundary



Evaluation focuses on whether Maintenance Autopilot selects a safe and appropriate \*\*next decision\*\*.



It does not require the system to identify the exact physical root cause of every reported symptom.



The primary evaluation question is:



> Given the available report and defined authority, what should happen next?



This distinction is important because a maintenance triage agent may correctly escalate, ask for information, or take a protective action without knowing the final technical diagnosis.



\## Generalization Claim



Maintenance Autopilot V2.5 is intended to generalize across realistic variations of ordinary residential maintenance reports within this operating envelope.



It does not claim universal maintenance competence.



Future independent evaluation should therefore introduce unseen wording, realistic ambiguity, symptom combinations and boundary cases while remaining inside this predefined operating envelope.



\## Prototype Status



Maintenance Autopilot V2.5 is a competition prototype.



It demonstrates an architecture for bounded autonomy using:



\- Strands Agents SDK

\- Amazon Bedrock

\- deterministic validation and policy logic

\- explicit human decision boundaries



It is not production property-management software and has not undergone production certification, regulatory approval or large-scale field validation.

