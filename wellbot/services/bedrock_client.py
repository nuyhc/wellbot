"""AWS Bedrock ConverseStream 클라이언트.

boto3를 사용하여 Bedrock Runtime의 ConverseStream API 호출.
동기 스트리밍 제너레이터와 비동기 래퍼를 제공.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Generator
from functools import lru_cache
from typing import Any

import boto3

from wellbot.services.config import ModelConfig

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_client() -> Any:
    """Bedrock Runtime 클라이언트를 생성한다 (싱글턴)."""
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


def _call_signature(name: str, tool_input: dict) -> tuple:
    """동일 호출 판정용 정규화 키."""
    inp = tool_input or {}
    query = (inp.get("query") or "").strip().lower()
    file_ids = tuple(sorted(int(x) for x in (inp.get("file_ids") or [])
                            if isinstance(x, (int, str)) and str(x).strip().lstrip("-").isdigit()))
    file_names = tuple(sorted(
        (n or "").strip().lower()
        for n in (inp.get("file_names") or [])
        if isinstance(n, str) and n.strip()
    ))
    return (name, query, file_ids, file_names)


def _strip_tool_result_meta(result_content: dict) -> dict:
    """Bedrock toolResult.content 에 _meta 같은 비표준 키가 들어가지 않도록 정제."""
    return {k: v for k, v in result_content.items() if not k.startswith("_")}


async def astream_chat_with_tools(
    messages: list[dict[str, Any]],
    model: ModelConfig,
    system_prompt: str,
    *,
    thinking_enabled: bool,
    tool_config: dict,
    tool_executor_fn,  # callable(name, input) -> dict (toolResult.content[0])
    max_iterations: int,
    empty_result_limit: int | None = None,
    duplicate_query_limit: int | None = None,
):
    """Tool use 루프를 내장한 스트리밍 래퍼.

    LLM 이 `tool_use` 로 종료하면:
      1. 누적된 toolUse block 을 assistant 메시지로 대화에 추가
      2. 각 toolUse 에 대해 tool_executor_fn 실행
      3. 결과를 user 메시지 (toolResult blocks) 로 추가
      4. 다시 LLM 호출 (최대 `max_iterations` 회)
    `end_turn` 또는 다른 이유로 종료하면 루프 종료.

    가드:
      - `duplicate_query_limit`: 동일 (name, query, file_ids, file_names)
        호출이 발생하면 LLM 우회하고 즉시 toolResult 주입.
      - `empty_result_limit`: 결과 0건이 연속 N회 발생하면 루프 강제 종료
        후 도구 비활성 폴백 답변 턴 1회 진행.
      - max_iterations 도달: 폴백 답변 턴 진입.

    Yields:
        ("thinking", str), ("text", str), ("usage", dict),
        ("tool_use", {name, input}),
        ("tool_result", {name, text}).
    """
    from wellbot.constants import (
        TOOL_USE_DUPLICATE_QUERY_LIMIT,
        TOOL_USE_EMPTY_RESULT_LIMIT,
    )

    if empty_result_limit is None:
        empty_result_limit = TOOL_USE_EMPTY_RESULT_LIMIT
    if duplicate_query_limit is None:
        duplicate_query_limit = TOOL_USE_DUPLICATE_QUERY_LIMIT

    bedrock_messages = _build_messages(messages)
    seen_calls: dict[tuple, int] = {}
    empty_streak = 0
    end_reason = "end_turn"

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

        # 정상 종료
        if stop_reason != "tool_use" or not pending_tool_uses:
            end_reason = stop_reason or "end_turn"
            log.info(
                "tool_loop end: smry_iter=%d reason=%s empty_streak=%d seen=%d",
                iteration, end_reason, empty_streak, len(seen_calls),
            )
            return

        # 한도 도달 → 폴백 답변 턴
        if iteration >= max_iterations:
            end_reason = "max_iter"
            log.info(
                "tool_loop forced fallback: reason=%s empty_streak=%d seen=%d",
                end_reason, empty_streak, len(seen_calls),
            )
            # assistant 의 마지막 tool_use 응답을 history 에 반영하지 않고 폴백 진입
            async for ev in _emit_no_tool_fallback(
                bedrock_messages, model, system_prompt, thinking_enabled,
                reason=end_reason,
            ):
                yield ev
            return

        # 1. assistant 턴 메시지로 추가
        if assistant_blocks:
            bedrock_messages.append(
                {"role": "assistant", "content": assistant_blocks}
            )

        # 2. 각 toolUse 실행 (중복/빈결과 가드 포함)
        tool_result_blocks: list[dict] = []
        for tu in pending_tool_uses:
            name = tu.get("name", "") or ""
            tool_input = tu.get("input", {}) or {}
            sig = _call_signature(name, tool_input)
            seen_calls[sig] = seen_calls.get(sig, 0) + 1

            if seen_calls[sig] > duplicate_query_limit:
                # 동일 호출 차단 - LLM 우회 즉시 합성 결과
                synthetic = {
                    "text": (
                        "동일한 쿼리/필터로 이미 검색한 호출입니다. "
                        "결과가 변하지 않으므로 재호출을 중단하고, "
                        "지금까지의 검색 결과로 사용자 질문에 답변하거나 "
                        "'관련 내용을 찾지 못함'을 안내하세요."
                    ),
                }
                tool_result_blocks.append({
                    "toolResult": {
                        "toolUseId": tu.get("toolUseId", ""),
                        "content": [synthetic],
                    }
                })
                yield ("tool_result", {"name": name, "text": synthetic["text"]})
                log.info("tool_loop duplicate blocked: sig=%s count=%d",
                         sig, seen_calls[sig])
                continue

            result_content = await asyncio.to_thread(
                tool_executor_fn, name, tool_input
            )
            meta = result_content.get("_meta") if isinstance(result_content, dict) else None
            result_count = (meta or {}).get("result_count", 0) if meta else 0
            if result_count == 0:
                empty_streak += 1
            else:
                empty_streak = 0

            sanitized = _strip_tool_result_meta(result_content)
            tool_result_blocks.append({
                "toolResult": {
                    "toolUseId": tu.get("toolUseId", ""),
                    "content": [sanitized],
                }
            })
            yield ("tool_result", {"name": name, "text": sanitized.get("text", "")})

            log.info(
                "tool_loop call: iter=%d name=%s sig=%s result_count=%d "
                "empty_streak=%d duplicate_count=%d",
                iteration, name, sig, result_count, empty_streak,
                seen_calls[sig],
            )

        bedrock_messages.append({"role": "user", "content": tool_result_blocks})

        # 연속 빈 결과 한도 초과 → 폴백 답변 턴
        if empty_streak >= empty_result_limit:
            end_reason = "empty_limit"
            log.info(
                "tool_loop forced fallback: reason=%s empty_streak=%d",
                end_reason, empty_streak,
            )
            async for ev in _emit_no_tool_fallback(
                bedrock_messages, model, system_prompt, thinking_enabled,
                reason=end_reason,
            ):
                yield ev
            return


async def _emit_no_tool_fallback(
    bedrock_messages: list[dict],
    model: ModelConfig,
    system_prompt: str,
    thinking_enabled: bool,
    *,
    reason: str,
):
    """도구 비활성 상태로 한 턴 더 호출해 사용자에게 답변을 전달."""
    if reason == "max_iter":
        guidance = (
            "추가 검색이 차단되었습니다 (호출 한도 도달). "
            "지금까지 누적된 toolResult 만 근거로 사용자 질문에 최대한 답하세요. "
            "근거가 부족하면 '첨부 파일에서 관련 내용을 찾지 못했다'고 명시하세요. "
            "이번 응답에서는 도구를 호출하지 마세요."
        )
    else:
        guidance = (
            "추가 검색이 차단되었습니다 (반복된 빈 결과). "
            "보유한 toolResult 또는 일반 지식으로 사용자 질문에 답하세요. "
            "관련 내용을 찾지 못했으면 그 사실을 솔직히 안내하세요. "
            "이번 응답에서는 도구를 호출하지 마세요."
        )

    augmented_system = (
        (system_prompt + "\n\n" if system_prompt else "") + guidance
    )

    gen = _stream_one_turn_iter(
        bedrock_messages,
        model,
        augmented_system,
        thinking_enabled,
        tool_config=None,
    )

    yielded_any_text = False
    while True:
        has_value, value = await asyncio.to_thread(_safe_next, gen)
        if not has_value:
            break
        event_type, payload = value  # type: ignore[misc]
        if event_type == "text":
            yielded_any_text = True
            yield ("text", payload)
        elif event_type == "thinking":
            yield ("thinking", payload)
        elif event_type == "usage":
            yield ("usage", payload)
        # tool_use / assistant_content / stop_reason 무시 (도구 비활성)

    if not yielded_any_text:
        # 폴백 자체가 비었으면 최소한의 안내 송출
        yield (
            "text",
            "첨부 파일에서 관련 내용을 찾지 못했습니다. 다른 표현으로 다시 질문해 주세요.",
        )
