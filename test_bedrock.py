import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
MODEL_ID = "us.amazon.nova-2-lite-v1:0"

client = boto3.client(
    "bedrock-runtime",
    region_name=REGION
)

try:
    response = client.converse(
        modelId=MODEL_ID,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": "Reply with exactly these three words: PYTHON BEDROCK WORKS"
                    }
                ],
            }
        ],
    )

    answer = response["output"]["message"]["content"][0]["text"]
    print(answer)

except ClientError as e:
    print("BEDROCK ERROR:")
    print(e)