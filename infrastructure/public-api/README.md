# Maintenance Autopilot public API

This standalone CDK application intentionally does not modify the generated
AgentCore infrastructure. It creates an API Gateway HTTP API and one Python
Lambda for `POST /api/evaluate`.

The Lambda accepts only `{"report":"..."}` and constructs the trusted runtime
payload using the canonical competition Demo Property (`U4`, $200 authority).
It calls `bedrock-agentcore:InvokeAgentRuntime` with the configured runtime ARN,
a server-generated runtime session ID, and this body:

```json
{"request":"...","unit":"U4","clarification":"","case_id":"..."}
```

The AgentCore response is allowlisted and normalized before it reaches the
browser. Unknown outcomes/rules and malformed responses fail closed.

The API stack is deployed separately from `MaintAutopilot/agentcore/cdk` so
AgentCore CLI regeneration cannot overwrite this integration.
