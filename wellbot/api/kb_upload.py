"""
kb_upload.py — KB 파일 업로드 커스텀 API

rx.upload의 10MB 제한을 우회하기 위한 FastAPI 엔드포인트.
파일을 수신하면 바로 S3에 업로드하고, 메타데이터를 반환.
Reflex state에서는 이 메타데이터로 pending_files를 업데이트하고,
confirm_upload 시 ingestion만 트리거.

처리 흐름:
    - pptx: json으로 변환 후 업로드 (Bedrock KB 미지원 형식)
    - xlsx/csv: 행 기준 분할 업로드
    - 그 외: 단일 업로드

엔드포인트:
    POST /api/upload_kb_files
    - multipart/form-data
    - files: 파일 목록 (최대 5개)
    - emp_no: 사용자 사번
    - upload_target: "personal" | "team"
    - dept_cd: 부서코드 (upload_target="team" 일 때 필수)

응답:
    {
        "uploaded": [
            {"name": "report.pdf", "size": 2100000, "s3_uri": "s3://bucket/..."},
            ...
        ],
        "error": null
    }
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import boto3
from fastapi import APIRouter, Cookie, File, Form, HTTPException, UploadFile, status

from wellbot.services.auth import auth_service
from wellbot.services.knowledgebase.config import get_kb_config
from wellbot.services.knowledgebase.kb_utils import (
    CONVERTIBLE_EXTS,
    SUPPORTED_EXTENSIONS,
    TABULAR_EXTS,
    convert_pptx_to_json,
    get_originals_prefix,
    split_and_upload_tabular,
    validate_file_size,
)
from wellbot.services.knowledgebase.team_kb_manager import get_dept_cd

log = logging.getLogger(__name__)

router = APIRouter()


@lru_cache(maxsize=1)
def _get_s3():
    """S3 클라이언트 (싱글턴)."""
    return boto3.client("s3")


@router.post("/api/upload_kb_files")
async def upload_kb_files(
    files: list[UploadFile] = File(...),
    upload_target: str = Form("personal"),
    wellbot_auth: str | None = Cookie(default=None),
):
    """
    파일을 S3에 바로 업로드.
    - pptx: json으로 변환 후 업로드 (Bedrock KB 미지원 형식)
    - xlsx/csv: 분할 업로드
    - personal: s3://{bucket}/users/{emp_no}/raw/{filename}
    - team:     s3://{bucket}/teams/{dept_cd}/raw/{filename}

    emp_no / dept_cd 는 클라이언트 입력을 신뢰하지 않고 wellbot_auth 세션
    쿠키에서 서버가 도출한다 (타인 KB 에 임의 파일 주입 방지).
    """
    # 1. 인증 — 세션 쿠키에서 emp_no 도출
    if not wellbot_auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다.",
        )
    user = auth_service.validate_session_token(wellbot_auth)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="세션이 만료되었습니다. 다시 로그인해주세요.",
        )
    emp_no = user["emp_no"]

    if len(files) > 5:
        return {"uploaded": [], "error": "한 번에 최대 5개 파일만 업로드 가능합니다."}

    # 2. 업로드 경로 결정 — team 은 본인 소속 부서로만 (서버에서 도출)
    if upload_target == "team":
        dept_cd = get_dept_cd(emp_no)
        if not dept_cd:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="소속 팀 정보가 없어 팀 업로드를 할 수 없습니다.",
            )
        prefix = f"teams/{dept_cd}/raw/"
    else:
        prefix = f"users/{emp_no}/raw/"

    kb_cfg = get_kb_config().get("personal_kb", {})
    bucket = kb_cfg.get("s3_bucket", "")
    if not bucket:
        return {"uploaded": [], "error": "S3 버킷 설정이 없습니다."}

    s3 = _get_s3()
    uploaded = []

    try:
        for file in files:
            ext = Path(file.filename).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                return {
                    "uploaded": uploaded,
                    "error": f"지원하지 않는 파일 형식: {file.filename}",
                }

            data = await file.read()
            filename = file.filename

            try:
                validate_file_size(data, filename)
            except ValueError as e:
                return {"uploaded": uploaded, "error": str(e)}

            if ext in CONVERTIBLE_EXTS:
                # 원본은 raw/ 밖의 originals/ 에 저장 (Bedrock 인덱싱 대상에서 제외)
                originals_prefix = get_originals_prefix(prefix)
                original_key = f"{originals_prefix}{filename}"
                s3.put_object(Bucket=bucket, Key=original_key, Body=data)
                data, filename = convert_pptx_to_json(data, filename)
                ext = ".json"

            if ext in TABULAR_EXTS:
                uris = split_and_upload_tabular(bucket, prefix, data, filename)
                for uri in uris:
                    uploaded.append({"name": filename, "size": len(data), "s3_uri": uri})
            else:
                key = f"{prefix}{filename}"
                s3.put_object(Bucket=bucket, Key=key, Body=data)
                uploaded.append({
                    "name": filename,
                    "size": len(data),
                    "s3_uri": f"s3://{bucket}/{key}",
                })

        return {"uploaded": uploaded, "error": None}

    except Exception as e:
        log.exception("KB API 업로드 실패")
        for item in uploaded:
            try:
                key = item["s3_uri"].replace(f"s3://{bucket}/", "")
                s3.delete_object(Bucket=bucket, Key=key)
            except Exception:
                pass
        return {"uploaded": [], "error": str(e)}
