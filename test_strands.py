from strands import Agent
from strands.models import BedrockModel

model = BedrockModel(
    model_id="us.amazon.nova-2-lite-v1:0",
    region_name="us-east-1",
)

agent = Agent(model=model)

response = agent(
    "Reply with exactly these three words: STRANDS BEDROCK WORKS"
)

print(response)