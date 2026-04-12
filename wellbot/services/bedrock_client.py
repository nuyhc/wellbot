"""AWS Bedrock ConverseStream 클라이언트.

boto3를 사용하여 Bedrock Runtime의 ConverseStream API를 호출한다.
동기 스트리밍 제너레이터와 비동기 래퍼를 제공한다.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from typing import Any

import boto3

from wellbot.services.config import ModelConfig


def _get_client() -> Any:
    """Bedrock Runtime 클라이언트를 생성한다."""
    region = os.environ.get(
        "AWS_REGION",
        os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )
    return boto3.client("bedrock-runtime", region_name=region)


def _build_messages(messages: list[dict[str, str]]) -> list[dict]:
    """ChatState 메시지를 Bedrock Converse 형식으로 변환한다."""
    result: list[dict] = []
    for msg in messages:
        role = msg["role"]
        if role not in ("user", "assistant"):
            continue
        result.append({
            "role": role,
            "content": [{"text": msg["content"]}],
        })
    return result


def stream_chat(
    messages: list[dict[str, str]],
    model: ModelConfig,
    system_prompt: str = "",
    *,
    thinking_enabled: bool = True,
) -> Generator[tuple[str, str], None, None]:
    """Bedrock ConverseStream API를 호출하여 청크를 yield한다.

    Yields:
        ("thinking", text) 또는 ("text", text) 튜플.
    """
    client = _get_client()
    bedrock_messages = _build_messages(messages)

    kwargs: dict[str, Any] = {
        "modelId": model.model_id,
        "messages": bedrock_messages,
        "inferenceConfig": {
            "maxTokens": model.max_tokens,
        },
    }

    if system_prompt:
        kwargs["system"] = [{"text": system_prompt}]

    # thinking 활성화 시 temperature는 생략 (Anthropic 제약: thinking 모드에서 temperature=1 고정)
    if model.thinking and model.thinking_budget > 0 and thinking_enabled:
        kwargs["additionalModelRequestFields"] = {
            "thinking": {
                "type": "enabled",
                "budget_tokens": model.thinking_budget,
            }
        }
    else:
        kwargs["inferenceConfig"]["temperature"] = model.temperature

    if model.top_p is not None:
        kwargs["inferenceConfig"]["topP"] = model.top_p

    response = client.converse_stream(**kwargs)

    for event in response["stream"]:
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})

            # 텍스트 응답
            if "text" in delta:
                yield ("text", delta["text"])

            # 사고 과정 (reasoningContent 형식)
            elif "reasoningContent" in delta:
                rc = delta["reasoningContent"]
                text = rc.get("text", "") if isinstance(rc, dict) else str(rc)
                if text:
                    yield ("thinking", text)

        # 토큰 사용량 (스트림 마지막에 반환됨)
        elif "metadata" in event:
            usage = event["metadata"].get("usage", {})
            if usage:
                yield ("usage", usage)


def _safe_next(
    gen: Generator[tuple[str, str], None, None],
) -> tuple[bool, tuple[str, str] | None]:
    """StopIteration을 안전하게 처리하는 next() 래퍼."""
    try:
        return (True, next(gen))
    except StopIteration:
        return (False, None)


async def astream_chat(
    messages: list[dict[str, str]],
    model: ModelConfig,
    system_prompt: str = "",
    *,
    thinking_enabled: bool = True,
):
    """비동기 스트리밍 래퍼.

    동기 stream_chat을 asyncio.to_thread로 감싸서
    이벤트 루프를 블로킹하지 않고 청크를 yield한다.

    Yields:
        ("thinking", text) 또는 ("text", text) 튜플.
    """
    gen = stream_chat(messages, model, system_prompt, thinking_enabled=thinking_enabled)
    while True:
        has_value, value = await asyncio.to_thread(_safe_next, gen)
        if not has_value:
            break
        yield value  # type: ignore[misc]
