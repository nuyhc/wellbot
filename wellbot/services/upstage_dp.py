"""Upstage Document Parse API 클라이언트.

프레젠테이션 파일(PPT/PPTX)을 Upstage Document Parse API로 파싱하여
텍스트로 변환한다.
"""

import os

import httpx

_API_URL = "https://api.upstage.ai/v1/document-ai/document-parse"
_TIMEOUT = 120.0  # 대용량 파일 처리를 위한 넉넉한 타임아웃


async def parse_document(file_bytes: bytes, filename: str) -> str:
    """Upstage Document Parse API를 호출하여 문서를 텍스트로 변환한다.

    Args:
        file_bytes: 파일 바이트 데이터
        filename: 원본 파일명 (MIME 타입 추론용)

    Returns:
        파싱된 텍스트 문자열

    Raises:
        ValueError: API 키 미설정, API 에러, 또는 100페이지 초과 시
    """
    api_key = os.getenv("UPSTAGE_API_KEY", "")
    if not api_key:
        raise ValueError("UPSTAGE_API_KEY가 설정되지 않았습니다.")

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"document": (filename, file_bytes)},
        )

    if resp.status_code != 200:
        raise ValueError(
            f"Upstage Document Parse API 오류 (HTTP {resp.status_code}): "
            f"{resp.text[:200]}"
        )

    data = resp.json()

    pages = data.get("usage", {}).get("pages", 0)
    if pages > 100:
        raise ValueError(
            f"프레젠테이션이 100페이지를 초과합니다 ({pages}페이지). "
            "100페이지 이하의 파일만 지원됩니다."
        )

    content = data.get("content", {})
    text = content.get("text", "")
    if not text:
        raise ValueError("Upstage Document Parse에서 텍스트를 추출하지 못했습니다.")

    return text
