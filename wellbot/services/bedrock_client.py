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


# Bedrock Converse 가 지원하는 이미지 포맷 집합
_BEDROCK_IMAGE_FORMATS = {"png", "jpeg", "gif", "webp"}


def image_format(filename: str) -> str | None:
    """공개 API: 파일명에서 Bedrock Converse image format 판별."""
    return _image_format(filename)


def _image_format(filename: str) -> str | None:
    """파일명 확장자에서 Bedrock Converse image format 을 판별한다."""
    from pathlib import Path

    ext = Path(filename).suffix.lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    if ext in _BEDROCK_IMAGE_FORMATS:
        return ext
    return None


def _build_messages(messages: list[dict[str, Any]]) -> list[dict]:
    """ChatState 메시지를 Bedrock Converse 형식으로 변환한다.

    각 메시지의 `content` 는 문자열이지만, `image_blocks` 필드가 있으면
    해당 content 배열에 `{"image": {...}}` block 을 함께 포함시킨다.

    image_blocks 스키마:
        [{"format": "png|jpeg|gif|webp", "bytes": <bytes>}]
    """
    result: list[dict] = []
    for msg in messages:
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue

        content_blocks: list[dict] = []

        # 이미지 블록은 텍스트보다 앞에 배치 (Anthropic 권장)
        for img in msg.get("image_blocks", []) or []:
            fmt = img.get("format")
            data = img.get("bytes")
            if not fmt or not data:
                continue
            content_blocks.append({
                "image": {
                    "format": fmt,
                    "source": {"bytes": data},
                }
            })

        text = msg.get("content", "") or ""
        # 텍스트는 비어있더라도 최소 하나의 content block 필요
        if text or not content_blocks:
            content_blocks.append({"text": text or " "})

        result.append({"role": role, "content": content_blocks})
    return result


def _stream_one_turn(
    bedrock_messages: list[dict],
    model: ModelConfig,
    system_prompt: str,
    *,
    thinking_enabled: bool,
    tool_config: dict | None,
) -> Generator[tuple[str, Any], None, None]:
    """단일 Converse 호출 (LLM 한 턴).

    Yields:
        ("thinking", text)                   — reasoning delta
        ("text", text)                       — 응답 텍스트 delta
        ("tool_use", {id, name, input})      — 완성된 tool use 요청
        ("assistant_content", blocks)        — 어시스턴트 응답 블록 목록
                                                (재호출을 위한 messages append 용)
        ("stop_reason", reason)              — "end_turn" | "tool_use" | ...
        ("usage", dict)                      — 토큰 사용량
    """
    client = _get_client()

    kwargs: dict[str, Any] = {
        "modelId": model.model_id,
        "messages": bedrock_messages,
        "inferenceConfig": {
            "maxTokens": model.max_tokens,
        },
    }
    if system_prompt:
        kwargs["system"] = [{"text": system_prompt}]
    if tool_config:
        kwargs["toolConfig"] = tool_config

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

    # 스트림 파싱 상태
    # contentBlockIndex -> 해당 블록의 누적 정보
    blocks: dict[int, dict] = {}
    text_accum: list[str] = []
    stop_reason: str | None = None

    for event in response["stream"]:
        if "contentBlockStart" in event:
            idx = event["contentBlockStart"].get("contentBlockIndex", 0)
            start = event["contentBlockStart"].get("start", {}) or {}
            if "toolUse" in start:
                tu = start["toolUse"]
                blocks[idx] = {
                    "type": "tool_use",
                    "toolUseId": tu.get("toolUseId", ""),
                    "name": tu.get("name", ""),
                    "input_buffer": "",
                }
            else:
                blocks[idx] = {"type": "text", "text": ""}

        elif "contentBlockDelta" in event:
            idx = event["contentBlockDelta"].get("contentBlockIndex", 0)
            delta = event["contentBlockDelta"].get("delta", {})

            # 텍스트
            if "text" in delta:
                txt = delta["text"]
                text_accum.append(txt)
                blk = blocks.setdefault(idx, {"type": "text", "text": ""})
                if blk.get("type") == "text":
                    blk["text"] += txt
                yield ("text", txt)

            # reasoning
            elif "reasoningContent" in delta:
                rc = delta["reasoningContent"]
                rtxt = rc.get("text", "") if isinstance(rc, dict) else str(rc)
                if rtxt:
                    yield ("thinking", rtxt)

            # tool use input (부분 JSON)
            elif "toolUse" in delta:
                tu_delta = delta["toolUse"]
                blk = blocks.get(idx)
                if blk and blk.get("type") == "tool_use":
                    partial = tu_delta.get("input", "")
                    if partial:
                        blk["input_buffer"] += partial

        elif "contentBlockStop" in event:
            idx = event["contentBlockStop"].get("contentBlockIndex", 0)
            blk = blocks.get(idx)
            if blk and blk.get("type") == "tool_use":
                # 누적 JSON 파싱
                from wellbot.services.tool_executor import parse_tool_input

                parsed = parse_tool_input(blk.get("input_buffer", "") or "{}")
                blk["input"] = parsed
                yield (
                    "tool_use",
                    {
                        "toolUseId": blk.get("toolUseId", ""),
                        "name": blk.get("name", ""),
                        "input": parsed,
                    },
                )

        elif "messageStop" in event:
            stop_reason = event["messageStop"].get("stopReason")

        elif "metadata" in event:
            usage = event["metadata"].get("usage", {})
            if usage:
                yield ("usage", usage)

    # 어시스턴트 응답을 재호출용 블록으로 재구성
    ordered_indices = sorted(blocks.keys())
    assistant_blocks: list[dict] = []
    for i in ordered_indices:
        blk = blocks[i]
        if blk.get("type") == "text" and blk.get("text"):
            assistant_blocks.append({"text": blk["text"]})
        elif blk.get("type") == "tool_use":
            assistant_blocks.append(
                {
                    "toolUse": {
                        "toolUseId": blk.get("toolUseId", ""),
                        "name": blk.get("name", ""),
                        "input": blk.get("input", {}),
                    }
                }
            )
    if assistant_blocks:
        yield ("assistant_content", assistant_blocks)

    yield ("stop_reason", stop_reason or "end_turn")


def stream_chat(
    messages: list[dict[str, Any]],
    model: ModelConfig,
    system_prompt: str = "",
    *,
    thinking_enabled: bool = True,
) -> Generator[tuple[str, Any], None, None]:
    """Bedrock ConverseStream API를 호출하여 청크를 yield한다 (tool use 없음).

    Yields:
        ("thinking", text) 또는 ("text", text) 또는 ("usage", dict) 튜플.
    """
    bedrock_messages = _build_messages(messages)
    for event_type, payload in _stream_one_turn(
        bedrock_messages,
        model,
        system_prompt,
        thinking_enabled=thinking_enabled,
        tool_config=None,
    ):
        if event_type in ("text", "thinking", "usage"):
            yield (event_type, payload)
        # assistant_content / stop_reason / tool_use 는 비-tool 모드에서 무시


from wellbot.constants import (
    TITLE_MAX_TOKENS,
    TITLE_MODEL_ID,
    TITLE_SYSTEM_PROMPT,
    TITLE_TEMPERATURE,
)


def generate_title(user_msg: str, assistant_msg: str) -> str:
    """경량 모델로 대화 제목을 생성한다."""
    client = _get_client()
    messages = [
        {
            "role": "user",
            "content": [{"text": f"질문: {user_msg}\n\n답변: {assistant_msg}"}],
        },
    ]
    try:
        response = client.converse(
            modelId=TITLE_MODEL_ID,
            messages=messages,
            system=[{"text": TITLE_SYSTEM_PROMPT}],
            inferenceConfig={"maxTokens": TITLE_MAX_TOKENS, "temperature": TITLE_TEMPERATURE},
        )
        output = response.get("output", {})
        content = output.get("message", {}).get("content", [])
        if content and "text" in content[0]:
            return content[0]["text"].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def _safe_next(
    gen: Generator[tuple[str, str], None, None],
) -> tuple[bool, tuple[str, str] | None]:
    """StopIteration을 안전하게 처리하는 next() 래퍼."""
    try:
        return (True, next(gen))
    except StopIteration:
        return (False, None)


async def astream_chat(
    messages: list[dict[str, Any]],
    model: ModelConfig,
    system_prompt: str = "",
    *,
    thinking_enabled: bool = True,
):
    """비동기 스트리밍 래퍼.

    동기 stream_chat을 asyncio.to_thread로 감싸서
    이벤트 루프를 블로킹하지 않고 청크를 yield한다.

    Yields:
        ("thinking", text) 또는 ("text", text) 또는 ("usage", dict) 튜플.
    """
    gen = stream_chat(messages, model, system_prompt, thinking_enabled=thinking_enabled)
    while True:
        has_value, value = await asyncio.to_thread(_safe_next, gen)
        if not has_value:
            break
        yield value  # type: ignore[misc]


def _stream_one_turn_iter(
    bedrock_messages: list[dict],
    model: ModelConfig,
    system_prompt: str,
    thinking_enabled: bool,
    tool_config: dict | None,
):
    """_stream_one_turn 을 generator 로 래핑한다 (to_thread 용)."""
    yield from _stream_one_turn(
        bedrock_messages,
        model,
        system_prompt,
        thinking_enabled=thinking_enabled,
        tool_config=tool_config,
    )


async def astream_chat_with_tools(
    messages: list[dict[str, Any]],
    model: ModelConfig,
    system_prompt: str,
    *,
    thinking_enabled: bool,
    tool_config: dict,
    tool_executor_fn,  # callable(name, input) -> dict (toolResult.content[0])
    max_iterations: int,
):
    """Tool use 루프를 내장한 스트리밍 래퍼.

    LLM 이 `tool_use` 로 종료하면:
      1. 누적된 toolUse block 을 assistant 메시지로 대화에 추가
      2. 각 toolUse 에 대해 tool_executor_fn 실행
      3. 결과를 user 메시지 (toolResult blocks) 로 추가
      4. 다시 LLM 호출 (최대 `max_iterations` 회)
    `end_turn` 또는 다른 이유로 종료하면 루프 종료.

    Yields:
        ("thinking", str), ("text", str), ("usage", dict),
        ("tool_use", {name, input}),
        ("tool_result", {name, text}).
    """
    bedrock_messages = _build_messages(messages)

    for iteration in range(max_iterations + 1):
        gen = _stream_one_turn_iter(
            bedrock_messages,
            model,
            system_prompt,
            thinking_enabled,
            tool_config,
        )
        pending_tool_uses: list[dict] = []
        assistant_blocks: list[dict] = []
        stop_reason: str | None = None

        while True:
            has_value, value = await asyncio.to_thread(_safe_next, gen)
            if not has_value:
                break
            event_type, payload = value  # type: ignore[misc]

            if event_type == "text":
                yield ("text", payload)
            elif event_type == "thinking":
                yield ("thinking", payload)
            elif event_type == "usage":
                yield ("usage", payload)
            elif event_type == "tool_use":
                pending_tool_uses.append(payload)
                yield (
                    "tool_use",
                    {"name": payload.get("name"), "input": payload.get("input")},
                )
            elif event_type == "assistant_content":
                assistant_blocks = payload
            elif event_type == "stop_reason":
                stop_reason = payload

        # 종료 조건
        if stop_reason != "tool_use" or not pending_tool_uses:
            return
        if iteration >= max_iterations:
            # 최대 반복 초과 → 안내 텍스트 주고 종료
            yield (
                "text",
                "\n\n(도구 호출 횟수 한도에 도달하여 추가 검색을 중단합니다.)",
            )
            return

        # 1. assistant 턴 메시지로 추가 (toolUse 포함)
        if assistant_blocks:
            bedrock_messages.append(
                {"role": "assistant", "content": assistant_blocks}
            )

        # 2. 각 toolUse 에 대한 결과를 user 턴으로 추가
        tool_result_blocks: list[dict] = []
        for tu in pending_tool_uses:
            result_content = await asyncio.to_thread(
                tool_executor_fn, tu.get("name", ""), tu.get("input", {}) or {}
            )
            tool_result_blocks.append(
                {
                    "toolResult": {
                        "toolUseId": tu.get("toolUseId", ""),
                        "content": [result_content],
                    }
                }
            )
            yield (
                "tool_result",
                {
                    "name": tu.get("name"),
                    "text": result_content.get("text", ""),
                },
            )

        bedrock_messages.append({"role": "user", "content": tool_result_blocks})
        # 다음 반복에서 LLM 재호출
