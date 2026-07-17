"""report_maker 전용 Bedrock 호출 래퍼 (단일 진입점).

legacy 는 invoke_model(Anthropic 네이티브 body)을 5곳 이상에서 제각각 호출하고
예외 처리가 제각각이었다. 여기서 Converse API 기반 단일 헬퍼로 통합한다:
    - call_model : 단일 턴 텍스트
    - call_json  : 텍스트에서 JSON 객체 추출(구조화 응답)
    - stream_text: 토큰 스트리밍 제너레이터(아웃라인 생성용)
ThrottlingException 지수 백오프 재시도 + max_tokens 잘림 경고 포함.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from functools import lru_cache
from typing import Any, Iterator

import boto3
from botocore.config import Config

from wellbot.services.report_maker.config import get_config

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client(region: str, read_timeout: int) -> Any:
    """Bedrock Runtime 클라이언트 싱글턴.

    region 이 빈 문자열이면 AWS_REGION → AWS_DEFAULT_REGION → us-east-1 폴백.
    """
    resolved = region or os.environ.get(
        "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    )
    return boto3.client(
        "bedrock-runtime",
        region_name=resolved,
        config=Config(read_timeout=read_timeout),
    )


def _converse_content(content: list[dict], max_tokens: int, system: str = "") -> tuple[str, str]:
    """Converse 단일 턴 호출(임의 content 블록) → (텍스트, stopReason). 실패 시 ("", "error").

    ThrottlingException 지수 백오프 재시도 + max_tokens 잘림 경고를 한곳에 모은다.
    텍스트/이미지 호출이 모두 이 코어를 거쳐 동일한 에러 처리를 공유한다(예외를 올리지 않음).
    """
    cfg = get_config()
    client = _client(cfg.region, cfg.read_timeout_sec)
    kwargs: dict[str, Any] = {
        "modelId": cfg.model_id,
        "messages": [{"role": "user", "content": content}],
        "inferenceConfig": {"maxTokens": max_tokens},
    }
    if system:
        kwargs["system"] = [{"text": system}]

    for attempt in range(cfg.max_retries + 1):
        try:
            resp = client.converse(**kwargs)
            stop = resp.get("stopReason", "")
            if stop == "max_tokens":
                log.warning("report_maker 응답 잘림(max_tokens) model=%s", cfg.model_id)
            blocks = resp["output"]["message"]["content"]
            return "".join(b["text"] for b in blocks if "text" in b), stop
        except client.exceptions.ThrottlingException:
            if attempt < cfg.max_retries:
                wait = cfg.retry_base_delay_sec * (2 ** attempt)
                log.warning("report_maker throttling → %.1fs 후 재시도", wait)
                time.sleep(wait)
            else:
                log.exception("report_maker throttling 재시도 소진")
                return "", "error"
        except Exception:
            log.exception("report_maker Bedrock 호출 실패")
            return "", "error"
    return "", "error"


def _converse_raw(prompt: str, max_tokens: int, system: str = "") -> tuple[str, str]:
    """텍스트 단일 턴 → (텍스트, stopReason)."""
    return _converse_content([{"text": prompt}], max_tokens, system)


def call_model(prompt: str, max_tokens: int, system: str = "") -> str:
    """Converse 단일 턴 호출 → 응답 텍스트. 실패 시 빈 문자열."""
    return _converse_raw(prompt, max_tokens, system)[0]


def call_vision(image_bytes: bytes, image_format: str, prompt: str, max_tokens: int) -> str:
    """이미지 + 지시 프롬프트 → 추출 텍스트. 실패 시 빈 문자열(재시도·에러처리 공유).

    image_format: "jpeg" | "png" | "gif" | "webp" (Converse image block format).
    """
    content = [
        {"image": {"format": image_format, "source": {"bytes": image_bytes}}},
        {"text": prompt},
    ]
    return _converse_content(content, max_tokens)[0]


def invoke_compat(prompt: str, max_tokens: int, system: str = "") -> dict:
    """legacy invoke_model 응답 호환 dict 반환.

    포팅한 프롬프트 조립 코드가 ``resp["content"][0]["text"]`` /
    ``resp.get("stop_reason")`` 형태로 응답을 읽으므로, Converse 결과를 그 형태로
    감싸 원문 프롬프트 로직을 그대로 재사용한다.
    """
    text, stop = _converse_raw(prompt, max_tokens, system)
    return {"content": [{"text": text}], "stop_reason": stop}


def _extract_json_object(text: str) -> dict:
    """응답 텍스트에서 첫 JSON 객체를 추출. 실패 시 빈 dict."""
    if not text:
        return {}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        log.warning("report_maker JSON 파싱 실패")
        return {}


def call_json(prompt: str, max_tokens: int, system: str = "") -> dict:
    """call_model 후 JSON 객체로 파싱. 실패 시 빈 dict."""
    return _extract_json_object(call_model(prompt, max_tokens, system))


def stream_text(prompt: str, max_tokens: int, system: str = "") -> Iterator[str]:
    """Converse 스트리밍 → 텍스트 청크 제너레이터.

    호출부(State)가 토큰을 받아 UI 에 흘려보낸다. 오류 시 조용히 종료하지 않고
    예외를 올려 상위에서 사용자 메시지로 처리하게 한다.
    """
    cfg = get_config()
    client = _client(cfg.region, cfg.read_timeout_sec)
    kwargs: dict[str, Any] = {
        "modelId": cfg.model_id,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens},
    }
    if system:
        kwargs["system"] = [{"text": system}]

    resp = client.converse_stream(**kwargs)
    for event in resp.get("stream", []):
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            if "text" in delta:
                yield delta["text"]
        elif "messageStop" in event:
            if event["messageStop"].get("stopReason") == "max_tokens":
                log.warning("report_maker 스트림 잘림(max_tokens) model=%s", cfg.model_id)
