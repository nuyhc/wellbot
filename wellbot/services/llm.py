"""LLM API 호출 모듈"""
import json
from ..config.settings import bedrock_client


def invoke_claude(
    messages: list[tuple[str, str]],
    current_question: str,
    model_id: str,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    top_p: float = 0.9,
    top_k: int = 50
) -> str:
    api_messages = []
    for q, a in messages:
        api_messages.append(
            {"role": "user", "content": [{"type": "text", "text": q}]},
        )

        if a:
            api_messages.append(
                {"role": "assistant", "content": [{"type": "text", "text": a}]}
            )

    api_messages.append(
        {"role": "user", "content": [{"type": "text", "text": current_question}]}
    )

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "messages": api_messages
    })

    response = bedrock_client.invoke_model(
        body=body,
        modelId=model_id,
        accept="application/json",
        contentType="application/json"
    )

    model_response = json.loads(response["body"].read())
    return model_response["content"][0]["text"]


def invoke_nova(
    messages: list[tuple[str, str]],
    current_question: str,
    model_id: str,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    top_p: float = 0.9
) -> str:
    api_messages = []
    for q, a in messages:
        api_messages.append(
            {"role": "user", "content": [{"text": q}]}
        )

        if a:
            api_messages.append(
                {"role": "assistant", "content": [{"text": a}]}
            )

    api_messages.append(
        {"role": "user", "content": [{"text": current_question}]}
    )

    body = json.dumps({
        "messages": api_messages,
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
            "topP": top_p
        }
    })

    response = bedrock_client.invoke_model(
        body=body,
        modelId=model_id,
        accept="application/json",
        contentType="application/json"
    )

    model_response = json.loads(response["body"].read())
    return model_response["output"]["message"]["content"][0]["text"]
