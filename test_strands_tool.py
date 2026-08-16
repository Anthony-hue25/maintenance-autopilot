from strands import Agent, tool
from strands.models import BedrockModel


@tool
def get_property_details(unit_id: str) -> str:
    """
    Look up details for a rental property unit.

    Args:
        unit_id: The rental unit identifier, for example "Unit 4".

    Returns:
        Property details including the owner's autonomous repair limit.
    """

    print(f"\nTOOL CALLED: get_property_details({unit_id})")

    properties = {
        "Unit 4": {
            "repair_authority": 200,
            "property_type": "2-bedroom apartment"
        },
        "Unit 7": {
            "repair_authority": 350,
            "property_type": "3-bedroom townhouse"
        }
    }

    if unit_id not in properties:
        return "PROPERTY_NOT_FOUND"

    property_data = properties[unit_id]

    return (
        f"{unit_id} is a {property_data['property_type']}. "
        f"The owner's autonomous repair authority is "
        f"${property_data['repair_authority']}."
    )


model = BedrockModel(
    model_id="us.amazon.nova-2-lite-v1:0",
    region_name="us-east-1",
)

agent = Agent(
    model=model,
    tools=[get_property_details]
)

agent(
    "What is the autonomous repair authority for Unit 4? "
    "You must use the property lookup tool to answer."
)