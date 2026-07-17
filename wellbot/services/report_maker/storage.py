"""report_maker 파일 저장/조회 (S3).

S3 의존을 이 파일 하나로 격리한다. 앱의 storage_service(범용 S3 유틸)를 재사용하되,
report_maker prefix 규칙(emp_no·템플릿 스코프)만 노출한다. 신원(emp_no)은 항상 서버가
세션에서 도출한 값이어야 한다(클라이언트 문자열 신뢰 금지 — legacy IDOR 해소).

prefix: {S3_KEY_PREFIX}/report_maker/{emp_no}/{template}/
  input/style_docs/{ts}_{name}   스타일 학습 참고 문서
  input/{ts}_{name}              주제 첨부(선택)
  meta/combined_style.json       AgentCore 미가용 시 스타일 폴백
  meta/analyzed.json             스타일 분석 완료 파일 이력(중복 분석 방지)
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from wellbot.constants import KST
from wellbot.services.files import storage_service

log = logging.getLogger(__name__)

_STYLE_DOCS = "input/style_docs"
_META_COMBINED = "meta/combined_style.json"
_META_ANALYZED = "meta/analyzed.json"


def _base_prefix() -> str:
    root = os.environ.get("S3_KEY_PREFIX", "files").strip("/")
    return f"{root}/report_maker" if root else "report_maker"


def template_prefix(emp_no: str, template: str) -> str:
    return f"{_base_prefix()}/{emp_no}/{template}/"


def _safe_name(filename: str) -> str:
    """경로 조작 차단 — basename 만 취한다 (H1/H2)."""
    return os.path.basename(filename or "").strip() or "file"


# ──────────────────────────────────────────────────────────────
# 입력 파일
# ──────────────────────────────────────────────────────────────
def save_style_doc(emp_no: str, template: str, filename: str, data: bytes) -> str:
    """스타일 학습용 참고 문서를 S3 에 저장하고 key 반환."""
    ts = datetime.now(tz=KST).strftime("%y%m%d%H%M%S")
    key = f"{template_prefix(emp_no, template)}{_STYLE_DOCS}/{ts}_{_safe_name(filename)}"
    storage_service.upload_bytes(data, key, content_type="application/octet-stream")
    log.info("스타일 문서 저장 emp_no=%s key=%s", emp_no, key)
    return key


def list_style_docs(emp_no: str, template: str) -> list[str]:
    """스타일 학습 문서 key 목록 (최근순)."""
    prefix = f"{template_prefix(emp_no, template)}{_STYLE_DOCS}/"
    metas = storage_service.list_objects_with_meta(prefix)
    metas.sort(key=lambda o: o.get("last_modified") or 0, reverse=True)
    return [o["key"] for o in metas]


def download_to_temp(s3_key: str) -> str:
    """S3 객체를 임시 파일로 내려받아 로컬 경로 반환 (파싱용).

    무작위 이름(mkstemp)으로 만들어 동시 사용자 간 충돌·경로 조작을 차단(H2/H3).
    호출측이 사용 후 os.remove 로 정리한다.
    """
    suffix = Path(s3_key).suffix.lower()
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="rptmk_")
    os.close(fd)
    storage_service.download_to_file(s3_key, Path(path))
    return path


# ──────────────────────────────────────────────────────────────
# 스타일 폴백 (AgentCore 미가용 시)
# ──────────────────────────────────────────────────────────────
def load_combined_style(emp_no: str, template: str) -> str:
    key = f"{template_prefix(emp_no, template)}{_META_COMBINED}"
    if not storage_service.object_exists(key):
        return ""
    try:
        data = json.loads(storage_service.download_bytes(key))
        return data.get("style_desc", "")
    except Exception:
        log.exception("combined_style.json 로드 실패 key=%s", key)
        return ""


def save_combined_style(emp_no: str, template: str, style_desc: str) -> None:
    key = f"{template_prefix(emp_no, template)}{_META_COMBINED}"
    body = json.dumps({"style_desc": style_desc}, ensure_ascii=False).encode("utf-8")
    storage_service.upload_bytes(body, key, content_type="application/json; charset=utf-8")
    log.info("combined_style 저장 emp_no=%s template=%s", emp_no, template)


# ──────────────────────────────────────────────────────────────
# 분석 이력 (중복 분석 방지)
# ──────────────────────────────────────────────────────────────
def get_analyzed_history(emp_no: str, template: str) -> set[str]:
    key = f"{template_prefix(emp_no, template)}{_META_ANALYZED}"
    if not storage_service.object_exists(key):
        return set()
    try:
        data = json.loads(storage_service.download_bytes(key))
        return set(data.get("analyzed", []))
    except Exception:
        log.exception("analyzed.json 로드 실패 key=%s", key)
        return set()


def save_analyzed_history(emp_no: str, template: str, analyzed: set[str]) -> None:
    key = f"{template_prefix(emp_no, template)}{_META_ANALYZED}"
    body = json.dumps({"analyzed": sorted(analyzed)}, ensure_ascii=False).encode("utf-8")
    storage_service.upload_bytes(body, key, content_type="application/json; charset=utf-8")


def delete_template_files(emp_no: str, template: str) -> int:
    """템플릿의 모든 S3 파일 삭제. 삭제 개수 반환."""
    return storage_service.delete_prefix(template_prefix(emp_no, template))
