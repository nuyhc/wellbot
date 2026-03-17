import os
import boto3
from dotenv import load_dotenv

load_dotenv()


bedrock_client = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "ap-northeast-2")
)