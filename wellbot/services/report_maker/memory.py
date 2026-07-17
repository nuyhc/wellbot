"""스타일 프로파일 영속 — Bedrock AgentCore 메모리 (+ S3 폴백).

설계 결정: AgentCore 유지. 다만 wellbot 기본 환경에 bedrock_agentcore 패키지가 없을 수
있으므로 지연·방어 import 한다. AgentCore 미가용(패키지 없음/memory_id 미설정/호출 실패)
시에는 storage.combined_style(S3) 로 자동 폴백해 서비스가 계속 동작한다.

actor_id 규약: f"{emp_no}_{to_safe_id(template)}"  (신원은 항상 서버 도출 emp_no)
네임스페이스: /writing/{actor_id}/ (문서 스타일), /preference/{actor_id}/ (선호·피드백)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from wellbot.services.report_maker import storage
from wellbot.services.report_maker.config import get_config
from wellbot.services.report_maker.parsing import to_safe_id

log = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))


def actor_id_for(emp_no: str, template: str) -> str:
    """AgentCore actor_id (emp_no·템플릿 스코프)."""
    return f"{emp_no}_{to_safe_id(template)}"


def _sanitize(text: str) -> str:
    return "".join(c for c in str(text) if not (0xD800 <= ord(c) <= 0xDFFF))


@lru_cache(maxsize=1)
def _mem_client():
    """AgentCore MemoryClient (지연 로드). 미가용 시 None."""
    cfg = get_config()
    try:
        from bedrock_agentcore.memory import MemoryClient  # type: ignore
    except Exception:
        log.warning("bedrock_agentcore 미설치 — AgentCore 스타일 메모리 비활성(S3 폴백)")
        return None
    try:
        return MemoryClient(region_name=cfg.region or None)
    except Exception:
        log.exception("MemoryClient 초기화 실패 — S3 폴백")
        return None


@lru_cache(maxsize=1)
def _ac_client():
    """bedrock-agentcore 클라이언트 (지연 로드). 미가용 시 None."""
    import boto3
    cfg = get_config()
    try:
        return boto3.client("bedrock-agentcore", region_name=cfg.region or None)
    except Exception:
        log.exception("bedrock-agentcore 클라이언트 생성 실패")
        return None


def _agentcore_ready() -> bool:
    return bool(get_config().memory_id) and _mem_client() is not None


def _create_event(actor_id: str, session_id: str, user_text: str, assistant_text: str) -> bool:
    """AgentCore 이벤트 저장. 성공 시 True."""
    cfg = get_config()
    ac = _ac_client()
    if ac is None or not cfg.memory_id:
        return False
    try:
        ac.create_event(
            memoryId=cfg.memory_id,
            actorId=actor_id,
            sessionId=session_id,
            eventTimestamp=datetime.now(_KST),
            payload=[
                {"conversational": {"role": "USER", "content": {"text": _sanitize(user_text)}}},
                {"conversational": {"role": "ASSISTANT", "content": {"text": assistant_text}}},
            ],
        )
        return True
    except Exception:
        log.exception("AgentCore create_event 실패 actor=%s", actor_id)
        return False


# ──────────────────────────────────────────────────────────────
# 저장
# ──────────────────────────────────────────────────────────────
def save_style(emp_no: str, template: str, style_desc: str) -> None:
    """문서 스타일 기록. AgentCore(/writing) + S3 combined_style 병행 저장.

    ASSISTANT role 에 스타일 텍스트를 두지 않고 USER 발화로 기록(userPreference
    전략이 USER 발화만 스캔 → semantic 오염 방지, legacy 규약 유지).
    """
    actor = actor_id_for(emp_no, template)
    session_id = f"style-{actor}-{datetime.now(_KST).strftime('%y%m%d%H%M%S')}"
    if _agentcore_ready():
        ok = _create_event(actor, session_id, f"[문서 스타일 기록]\n{style_desc}", "문서 스타일을 기록했습니다.")
        if ok:
            log.info("AgentCore writing 저장 actor=%s", actor)
    # S3 폴백/병행 저장 (AgentCore 미가용 시에도 스타일 유지)
    storage.save_combined_style(emp_no, template, style_desc)


def save_preference(emp_no: str, template: str, pref_text: str) -> None:
    """사용자 선호/피드백 기록 (AgentCore /preference)."""
    actor = actor_id_for(emp_no, template)
    session_id = f"pref-{actor}-{datetime.now(_KST).strftime('%y%m%d%H%M%S')}"
    if _agentcore_ready():
        ok = _create_event(
            actor, session_id,
            f"나는 다음과 같은 문서 작성 스타일을 선호합니다:\n{pref_text}",
            "선호도를 기억하겠습니다.",
        )
        if ok:
            log.info("AgentCore preference 저장 actor=%s", actor)


# ──────────────────────────────────────────────────────────────
# 로드
# ──────────────────────────────────────────────────────────────
def load_style(emp_no: str, template: str, top_k: int = 10) -> str:
    """스타일 프로파일 로드. AgentCore(/writing·/preference) → 없으면 S3 폴백."""
    cfg = get_config()
    actor = actor_id_for(emp_no, template)
    mem = _mem_client()

    if mem is not None and cfg.memory_id:
        parts: list[str] = []
        for namespace, label in [
            (f"/writing/{actor}/", "문서 스타일"),
            (f"/preference/{actor}/", "선호/피드백"),
        ]:
            try:
                resp = mem.list_memory_records(memory_id=cfg.memory_id, namespace=namespace)
                records = resp if isinstance(resp, list) else resp.get("memoryRecordSummaries", [])
                if not records:
                    continue
                records = sorted(
                    records,
                    key=lambda r: (r.get("createdAt", "") if isinstance(r, dict) else ""),
                    reverse=True,
                )[:top_k]
                lines = []
                for r in records:
                    content = r.get("content", "") if isinstance(r, dict) else str(r)
                    text = content.get("text", "") if isinstance(content, dict) else str(content)
                    if text:
                        lines.append(text)
                if lines:
                    parts.append(f"[{label}]\n" + "\n---\n".join(lines))
            except Exception:
                log.exception("AgentCore %s 로드 실패", label)
        if parts:
            return "\n\n".join(parts)

    # S3 combined_style.json 폴백
    return storage.load_combined_style(emp_no, template)
