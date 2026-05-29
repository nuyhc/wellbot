"""Bedrock Converse 이미지 포맷 판별 헬퍼."""

from __future__ import annotations

from pathlib import Path

# Bedrock Converse 가 지원하는 이미지 포맷 집합
_BEDROCK_IMAGE_FORMATS = {"png", "jpeg", "gif", "webp"}


def image_format(filename: str) -> str | None:
    """파일명 확장자에서 Bedrock Converse image format 을 판별한다."""
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    if ext in _BEDROCK_IMAGE_FORMATS:
        return ext
    return None
