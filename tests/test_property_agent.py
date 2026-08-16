from strands import Agent
from strands.models import BedrockModel

from app.tools import get_property_details


model = BedrockModel(
    model_id="us.amazon.nova-2-lite-v1:0",
    region_name="us-east-1",
)

agent = Agent(
    model=model,
    tools=[get_property_details],
)

agent(
    """
    Use the property tool to answer these three questions:

    1. What is U4's autonomous repair authority?
    2. What is U5's autonomous repair authority?
    3. Does U9 exist?

    Do not guess. Use the tool for each unit.
    """
)