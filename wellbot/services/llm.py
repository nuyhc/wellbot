"""LLM API 호출 모듈"""
import json
from collections.abc import Generator
from ..config.settings import bedrock_client


def _build_claude_messages(
    messages: list[tuple[str, str]], current_question: str
) -> list[dict]:
    api_messages = []
    for q, a in messages:
        api_messages.append(
            {"role": "user", "content": [{"type": "text", "text": q}]}
        )
        if a:
            api_messages.append(
                {"role": "assistant", "content": [{"type": "text", "text": a}]}
            )
    api_messages.append(
        {"role": "user", "content": [{"type": "text", "text": current_question}]}
    )
    return api_messages


def stream_claude(
    messages: list[tuple[str, str]],
    current_question: str,
    model_id: str,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> Generator[str, None, None]:
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": _build_claude_messages(messages, current_question)
    })

    response = bedrock_client.invoke_model_with_response_stream(
        body=body,
        modelId=model_id,
        accept="application/json",
        contentType="application/json"
    )

    for event in response["body"]:
        chunk = json.loads(event["chunk"]["bytes"])
        if chunk.get("type") == "content_block_delta":
            delta = chunk.get("delta", {})
            if delta.get("type") == "text_delta":
                yield delta.get("text", "")


def _build_nova_body(
    messages: list[tuple[str, str]],
    current_question: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
) -> str:
    api_messages = []
    for q, a in messages:
        api_messages.append({"role": "user", "content": [{"text": q}]})
        if a:
            api_messages.append({"role": "assistant", "content": [{"text": a}]})
    api_messages.append({"role": "user", "content": [{"text": current_question}]})

    return json.dumps({
        "messages": api_messages,
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
            "topP": top_p,
        }
    })


def stream_nova(
    messages: list[tuple[str, str]],
    current_question: str,
    model_id: str,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    top_p: float = 0.9,
) -> Generator[str, None, None]:
    body = _build_nova_body(messages, current_question, max_tokens, temperature, top_p)

    response = bedrock_client.invoke_model_with_response_stream(
        body=body,
        modelId=model_id,
        accept="application/json",
        contentType="application/json"
    )

    for event in response["body"]:
        chunk = json.loads(event["chunk"]["bytes"])
        delta = chunk.get("contentBlockDelta", {}).get("delta", {})
        text = delta.get("text", "")
        if text:
            yield text
