from strands import Agent
from strands.models import BedrockModel

from app.tools import check_repair_authority


model = BedrockModel(
    model_id="us.amazon.nova-2-lite-v1:0",
    region_name="us-east-1",
    temperature=0,
)

agent = Agent(
    model=model,
    tools=[check_repair_authority],
)

agent(
    """
    Use the authority tool for all three checks.

    1. U5 repair quote = $240
    2. U2 repair quote = $240
    3. U1 repair quote = $200

    Report whether each is within authority.
    """
)