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
    storage.save_combined_style(emp_no, template, desc)  # S3 정본(최종본) 덮어쓰기
    if _agentcore_ready():
        _delete_records(f"/writing/{actor}/")  # 기존 문서 스타일 레코드 제거(1개 유지)
        if desc.strip():
            session_id = f"style-{actor}-{datetime.now(_KST).strftime('%y%m%d%H%M%S')}"
            ok = _create_event(actor, session_id, f"[문서 스타일 기록]\n{desc}", "문서 스타일을 기록했습니다.")
            if ok:
                log.info("AgentCore writing 교체 저장 actor=%s", actor)


def _rebuild(emp_no: str, template: str, *, rebuild_base: bool = False) -> None:
    """뼈대(문서 desc 병합) + 세부조정(manual)을 합쳐 최종 combined 를 materialize.

    rebuild_base=True 면 문서 사이드카에서 뼈대를 다시 병합해 저장(문서 add/delete 시).
    False 면 저장된 뼈대를 재사용(manual 만 바뀐 경우). 최종본은 _replace_writing 으로
    S3 정본 + AgentCore /writing 에 반영해 조회(load_style)가 LLM 없이 읽게 한다.
    """
    if rebuild_base:
        base = ""
        for d in storage.load_style_doc_descs(emp_no, template).values():
            d = (d or "").strip()
            if d:
                base = style.merge_style_desc(base, d) if base else d
        storage.save_doc_base(emp_no, template, base)
    else:
        base = storage.load_doc_base(emp_no, template)

    manual = storage.load_style_manual(emp_no, template).strip()
    combined = style.merge_style_desc(base, manual) if (base and manual) else (base or manual)
    _replace_writing(emp_no, template, combined)


def save_style(emp_no: str, template: str, style_desc: str, doc_basename: str) -> None:
    """참고 문서 하나의 스타일을 뼈대 사이드카에 기록하고 뼈대·최종본을 재빌드.

    문서별 style_desc 를 사이드카({basename: desc})에 보관하므로, 이후 문서 삭제/교체 시
    남은 문서로 뼈대를 재빌드할 수 있다(수동 편집 레이어는 보존).
    """
    storage.save_style_doc_desc(emp_no, template, doc_basename, style_desc)
    _rebuild(emp_no, template, rebuild_base=True)


def delete_doc(emp_no: str, template: str, doc_basename: str) -> None:
    """참고 문서 하나 삭제 — 원본 파일 + 뼈대 사이드카 제거 후 뼈대·최종본 재빌드(세부조정 보존)."""
    storage.remove_style_doc_desc(emp_no, template, doc_basename)
    storage.delete_style_doc_file(emp_no, template, doc_basename)
    _rebuild(emp_no, template, rebuild_base=True)


def save_preference(emp_no: str, template: str, pref_text: str) -> None:
    """사용자 선호/피드백 기록 — S3 정본에 '단일 통합 가이드'로 병합(저장 시 LLM 1회) + AgentCore 병행.

    조회 때마다 요약하지 않도록, 저장 시점에 기존 S3 정본과 LLM 병합해 항상 하나의 정돈된
    가이드로 유지한다(save_style 과 동일 규약). 조회(load_style)는 이 정본을 그대로 읽어
    LLM 을 타지 않는다. AgentCore /preference 는 장기 semantic 메모리로 병행 축적한다.
    """
    actor = actor_id_for(emp_no, template)
    # 세부조정(manual) 레이어에 병합 — 뼈대(문서)는 건드리지 않고 그 위에 얹힘
    existing = storage.load_style_manual(emp_no, template)
    merged = style.merge_style_desc(existing, pref_text) if existing.strip() else pref_text
    storage.save_style_manual(emp_no, template, merged)
    _rebuild(emp_no, template, rebuild_base=False)
    # AgentCore /preference 병행 기록(가용 시) — 장기 semantic 메모리
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


def load_style(emp_no: str, template: str, top_k: int = 10, summarize: bool = True) -> str:
    """스타일 프로파일 로드 — S3 정본(단일 통합 가이드) 우선, 비면 AgentCore 폴백.

    저장 경로(save_style·save_preference·replace_style)가 S3 정본을 항상 '단일 통합
    가이드'로 병합 유지하므로, 조회는 **LLM 없이** 정본을 그대로 반환한다(편집기·세션 공통).
    AgentCore 는 저장 시 병행 기록되어 장기 semantic 메모리로 축적되며, 표시에는 병합하지
    않는다(조회마다 재요약 방지).

    S3 정본이 없을 때(옛/이관 데이터로 AgentCore 에만 있는 경우)만 폴백으로 AgentCore
    레코드를 읽고, 레코드가 여러 개이고 summarize=True 면 그때만 LLM 으로 정리한다.
    """
    combined = storage.load_combined_style(emp_no, template)
    if combined.strip():
        return combined

    # 폴백: S3 정본이 비어 있고 AgentCore 에만 기록이 있는 경우
    if _agentcore_ready():
        actor = actor_id_for(emp_no, template)
        texts: list[str] = []
        seen: set[str] = set()
        for namespace in (f"/writing/{actor}/", f"/preference/{actor}/"):
            recs = _record_summaries(namespace)
            if not recs:
                continue
            recs.sort(
                key=lambda r: r.get("createdAt") or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )
            for r in recs[:top_k]:
                t = _record_text(r).strip()
                if t and t not in seen:
                    seen.add(t)
                    texts.append(t)
        if texts:
            joined = "\n\n---\n\n".join(texts)
            if len(texts) == 1 or not summarize:
                return joined
            return style.summarize_style(joined)
    return ""


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
    """편집기 저장 — 세부조정(manual) 레이어를 편집 텍스트로 교체 후 재빌드(뼈대 보존).

    편집기는 세부조정 레이어만 편집하므로, 문서 뼈대(doc_base)는 그대로 두고 manual 만
    교체한 뒤 최종본(뼈대+세부조정)을 다시 materialize 한다. 문서 목록도 보존된다.
    """
    storage.save_style_manual(emp_no, template, text)
    _rebuild(emp_no, template, rebuild_base=False)
