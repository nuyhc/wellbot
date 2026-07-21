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

from wellbot.services.report_maker import storage, style
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
def _replace_writing(emp_no: str, template: str, desc: str) -> None:
    """문서 스타일을 desc 하나로 교체: S3 combined 덮어쓰기 + AgentCore /writing 레코드 교체.

    ASSISTANT role 에 스타일 텍스트를 두지 않고 USER 발화로 기록(userPreference
    전략이 USER 발화만 스캔 → semantic 오염 방지, legacy 규약 유지).
    """
    actor = actor_id_for(emp_no, template)
    storage.save_combined_style(emp_no, template, desc)  # S3 정본(단일) 덮어쓰기
    if _agentcore_ready():
        _delete_records(f"/writing/{actor}/")  # 기존 문서 스타일 레코드 제거(1개 유지)
        session_id = f"style-{actor}-{datetime.now(_KST).strftime('%y%m%d%H%M%S')}"
        ok = _create_event(actor, session_id, f"[문서 스타일 기록]\n{desc}", "문서 스타일을 기록했습니다.")
        if ok:
            log.info("AgentCore writing 교체 저장 actor=%s", actor)


def save_style(emp_no: str, template: str, style_desc: str) -> None:
    """문서 스타일 학습 — 기존 통합 스타일과 LLM 병합해 '템플릿당 1개'로 유지(legacy 규약).

    여러 참고 문서를 올려도 combined_style 은 항상 하나의 통합 가이드로 정제된다.
    S3 정본을 병합 기준으로 삼아(즉시성·결정성) AgentCore /writing 도 병합본 1개로 교체.
    """
    existing = storage.load_combined_style(emp_no, template)
    merged = style.merge_style_desc(existing, style_desc) if existing.strip() else style_desc
    _replace_writing(emp_no, template, merged)


def save_preference(emp_no: str, template: str, pref_text: str) -> None:
    """사용자 선호/피드백 기록 — S3 정본 누적(즉시·결정적) + AgentCore /preference(장기 메모리) 병행.

    학습(save_style)·편집(replace_style)과 동일하게 S3 정본을 항상 함께 쓴다. 이전엔
    AgentCore ON 일 때 /preference 에만 기록해(전략이 비동기 추출) 저장 직후 조회에 안 잡혔다.
    이제 S3 정본에 즉시 누적해 편집기·조회(load_style)에 곧바로 반영되고, AgentCore 는
    장기 semantic 메모리로 병행 축적한다.
    """
    actor = actor_id_for(emp_no, template)
    # S3 정본 즉시 누적(모든 모드) — 조회·편집기 즉시 반영
    storage.append_combined_style(emp_no, template, pref_text)
    # AgentCore /preference 병행 기록(가용 시) — 장기 semantic 메모리(권위)
    if _agentcore_ready():
        session_id = f"pref-{actor}-{datetime.now(_KST).strftime('%y%m%d%H%M%S')}"
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


def _split_combined(text: str) -> list[str]:
    """S3 정본(combined_style)을 누적 구분자로 청크 분해(load 병합·중복 제거용)."""
    return [c.strip() for c in (text or "").split("\n\n---\n\n") if c.strip()]


def load_style(emp_no: str, template: str, top_k: int = 10) -> str:
    """스타일 프로파일 로드 — AgentCore(권위·장기) + S3 정본(즉시·결정적) 병행 병합.

    AgentCore 레코드(/writing·/preference)를 우선 수집하고, S3 정본(combined_style)을
    같은 청크 단위로 합쳐 중복을 제거한다. AgentCore 전략은 비동기 추출이라 방금 저장한
    내용이 레코드로는 늦게 잡히지만, 저장 시 S3 정본에도 병행 기록되므로(save_style·
    save_preference·replace_style 모두) S3 청크가 그 갭을 즉시 메운다.

    청크가 여러 개일 때만 legacy 처럼 LLM 으로 핵심 지시 가이드로 정리(summarize_style)
    한다. 단일 청크(편집기 저장본 등)는 이미 정돈돼 있으므로 원문 그대로 노출한다
    (편집 round-trip 보존).
    """
    actor = actor_id_for(emp_no, template)
    chunks: list[str] = []
    seen: set[str] = set()

    def _add(text: str) -> None:
        t = (text or "").strip()
        if t and t not in seen:
            seen.add(t)
            chunks.append(t)

    # AgentCore 레코드(권위) 우선
    if _agentcore_ready():
        for namespace in (f"/writing/{actor}/", f"/preference/{actor}/"):
            recs = _record_summaries(namespace)
            if not recs:
                continue
            recs.sort(
                key=lambda r: r.get("createdAt") or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )
            for r in recs[:top_k]:
                _add(_record_text(r))

    # S3 정본(즉시) 병합 — AgentCore 추출 지연분/폴백을 즉시 커버(중복 청크는 스킵)
    for chunk in _split_combined(storage.load_combined_style(emp_no, template)):
        _add(chunk)

    if not chunks:
        return ""
    if len(chunks) == 1:
        return chunks[0]
    return style.summarize_style("\n\n---\n\n".join(chunks))


def _delete_records(namespace: str) -> int:
    """AgentCore namespace 의 모든 memory record 삭제. 삭제 개수 반환."""
    cfg = get_config()
    ac = _ac_client()
    if ac is None or not cfg.memory_id:
        return 0
    ids = [r.get("memoryRecordId") for r in _record_summaries(namespace)
           if r.get("memoryRecordId")]
    deleted = 0
    for i in range(0, len(ids), 100):
        batch = [{"memoryRecordId": rid} for rid in ids[i:i + 100]]
        try:
            resp = ac.batch_delete_memory_records(memoryId=cfg.memory_id, records=batch)
            deleted += len(resp.get("successfulRecords", []) or [])
        except Exception:
            log.exception("AgentCore batch_delete_memory_records 실패 ns=%s", namespace)
    return deleted


def clear_style(emp_no: str, template: str) -> int:
    """작성 스타일 초기화 — AgentCore /writing·/preference 레코드 + S3 스타일 파일 삭제.

    삭제한 AgentCore 레코드 수를 반환한다(S3 삭제는 storage.delete_style 이 담당).
    """
    actor = actor_id_for(emp_no, template)
    deleted = _delete_records(f"/writing/{actor}/") + _delete_records(f"/preference/{actor}/")
    storage.delete_style(emp_no, template)
    return deleted


def replace_style(emp_no: str, template: str, text: str) -> None:
    """작성 스타일 전체 교체(편집기 저장). 문서 스타일을 편집 텍스트 하나로 교체(멱등).

    병합 없이 그대로 교체하며, 학습 문서 목록(style_docs)은 보존한다(초기화와 구분).
    선호(/preference)는 편집 텍스트가 대체하므로 함께 비운다. AgentCore 는 비동기
    추출이라 교체 직후 목록에 안 보일 수 있으나, S3 정본은 즉시 반영된다.
    """
    actor = actor_id_for(emp_no, template)
    if _agentcore_ready():
        _delete_records(f"/preference/{actor}/")
    _replace_writing(emp_no, template, text)
