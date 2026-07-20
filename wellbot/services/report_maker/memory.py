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
def _ac_client():
    """bedrock-agentcore 데이터플레인 클라이언트(저수준 boto3, 지연 로드). 미가용 시 None.

    고수준 MemoryClient 는 버전에 따라 list/delete 레코드 API 가 없다(1.18.x 에서 제거).
    list_memory_records / batch_delete_memory_records / create_event 를 모두 제공하는
    저수준 boto3 클라이언트를 단일 진입점으로 쓴다(legacy 는 1.6.2 고수준 API 였음).
    """
    import boto3
    cfg = get_config()
    try:
        return boto3.client("bedrock-agentcore", region_name=cfg.region or None)
    except Exception:
        log.exception("bedrock-agentcore 클라이언트 생성 실패")
        return None


def _agentcore_ready() -> bool:
    return bool(get_config().memory_id) and _ac_client() is not None


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
    # S3 폴백/병행 저장 (AgentCore 미가용 시에도 스타일 유지). 여러 참고 문서를
    # 학습하면 누적되도록 append (편집기의 전체 덮어쓰기와 구분).
    storage.append_combined_style(emp_no, template, style_desc)


def save_preference(emp_no: str, template: str, pref_text: str) -> None:
    """사용자 선호/피드백 기록 (AgentCore /preference). 미가용 시 S3 폴백 누적."""
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
    else:
        # AgentCore 미가용 시에도 유실되지 않도록 S3 정본에 누적(무동작 방지).
        storage.append_combined_style(emp_no, template, pref_text)


# ──────────────────────────────────────────────────────────────
# 로드
# ──────────────────────────────────────────────────────────────
def _record_summaries(namespace: str) -> list[dict]:
    """AgentCore namespace 의 memory record 요약 전체(페이지네이션). 미가용/실패 시 []."""
    cfg = get_config()
    ac = _ac_client()
    if ac is None or not cfg.memory_id:
        return []
    out: list[dict] = []
    token = None
    try:
        while True:
            kw = {"memoryId": cfg.memory_id, "namespace": namespace, "maxResults": 100}
            if token:
                kw["nextToken"] = token
            resp = ac.list_memory_records(**kw)
            out.extend(resp.get("memoryRecordSummaries", []) or [])
            token = resp.get("nextToken")
            if not token:
                break
    except Exception:
        log.exception("AgentCore list_memory_records 실패 ns=%s", namespace)
    return out


def _record_text(r: dict) -> str:
    content = r.get("content") or {}
    return content.get("text", "") if isinstance(content, dict) else str(content)


def load_style(emp_no: str, template: str, top_k: int = 10) -> str:
    """스타일 프로파일 로드. AgentCore(/writing·/preference) 우선 → 없으면 S3 폴백.

    legacy 와 동일한 AgentCore-primary 구조. 단 고수준 MemoryClient 대신 저수준 boto3
    클라이언트의 list_memory_records 를 쓴다(1.18.x 호환). AgentCore 레코드는 전략이
    비동기 추출하므로 방금 기록한 내용이 즉시 안 보일 수 있어, 편집·즉시성이 필요한
    경로는 S3 정본(load_combined_style)을 병행한다.
    """
    actor = actor_id_for(emp_no, template)
    if _agentcore_ready():
        texts: list[str] = []
        for namespace in (f"/writing/{actor}/", f"/preference/{actor}/"):
            recs = _record_summaries(namespace)
            if not recs:
                continue
            recs.sort(
                key=lambda r: r.get("createdAt") or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )
            for r in recs[:top_k]:
                text = _record_text(r)
                if text:
                    texts.append(text)
        if texts:
            return "\n\n---\n\n".join(texts)

    # S3 combined_style.json 폴백
    return storage.load_combined_style(emp_no, template)


def clear_style(emp_no: str, template: str) -> int:
    """작성 가이드 초기화 — AgentCore /writing·/preference 레코드 + S3 스타일 파일 삭제.

    삭제한 AgentCore 레코드 수를 반환한다(S3 삭제는 storage.delete_style 이 담당).
    """
    actor = actor_id_for(emp_no, template)
    deleted = 0
    if _agentcore_ready():
        cfg = get_config()
        ac = _ac_client()
        for namespace in (f"/writing/{actor}/", f"/preference/{actor}/"):
            ids = [r.get("memoryRecordId") for r in _record_summaries(namespace)
                   if r.get("memoryRecordId")]
            for i in range(0, len(ids), 100):
                batch = [{"memoryRecordId": rid} for rid in ids[i:i + 100]]
                try:
                    resp = ac.batch_delete_memory_records(memoryId=cfg.memory_id, records=batch)
                    deleted += len(resp.get("successfulRecords", []) or [])
                except Exception:
                    log.exception("AgentCore batch_delete_memory_records 실패 ns=%s", namespace)
    storage.delete_style(emp_no, template)
    return deleted


def replace_style(emp_no: str, template: str, text: str) -> None:
    """작성 가이드 전체 교체(편집기 저장). 기존 기록 삭제 후 단일 기록으로 저장(멱등).

    AgentCore 는 비동기 추출이라 교체 직후 목록에 안 보일 수 있으나, S3 정본은 즉시
    반영되므로 편집기 재진입 시 방금 저장한 내용이 보인다.
    """
    clear_style(emp_no, template)
    save_style(emp_no, template, text)
