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

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

import boto3
from fastapi import APIRouter, File, Form, UploadFile

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

log = logging.getLogger(__name__)

router = APIRouter()


@lru_cache(maxsize=1)
def _get_s3():
    """S3 클라이언트 (싱글턴)."""
    return boto3.client("s3")


@router.post("/api/upload_kb_files")
async def upload_kb_files(
    files: list[UploadFile] = File(...),
    emp_no: str = Form(...),
    upload_target: str = Form("personal"),
    dept_cd: Optional[str] = Form(None),
):
    """
    파일을 S3에 바로 업로드.
    - pptx: json으로 변환 후 업로드 (Bedrock KB 미지원 형식)
    - xlsx/csv: 분할 업로드
    - personal: s3://{bucket}/users/{emp_no}/raw/{filename}
    - team:     s3://{bucket}/teams/{dept_cd}/raw/{filename}
    """

    if len(files) > 5:
        return {"uploaded": [], "error": "한 번에 최대 5개 파일만 업로드 가능합니다."}

    if upload_target == "team" and not dept_cd:
        return {"uploaded": [], "error": "팀 업로드 시 dept_cd가 필요합니다."}

    kb_cfg = get_kb_config().get("personal_kb", {})
    bucket = kb_cfg.get("s3_bucket", "")
    if not bucket:
        return {"uploaded": [], "error": "S3 버킷 설정이 없습니다."}

    s3 = _get_s3()
    uploaded = []
    prefix = f"teams/{dept_cd}/raw/" if upload_target == "team" else f"users/{emp_no}/raw/"

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
