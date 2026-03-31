"""콘텐츠 블록 빌더 모듈.

첨부 파일을 AWS Bedrock Converse API content block 형식으로 변환한다.
이미지는 ImageBlock, 문서는 DocumentBlock 형식으로 변환하며,
변환 실패한 파일은 건너뛰고 나머지만 반환한다.
"""

import os
from dataclasses import dataclass

# jpg → jpeg 매핑 (Converse API는 jpeg만 지원)
_FORMAT_MAP: dict[str, str] = {"jpg": "jpeg"}


@dataclass
class AttachedFile:
    """첨부 파일 데이터를 표현하는 데이터클래스."""

    filename: str  # 원본 파일명 (예: "photo.png")
    data: bytes  # 파일 바이트 데이터
    file_type: str  # 'image' 또는 'document'


def build_content_blocks(files: list[AttachedFile]) -> tuple[list[dict], list[str]]:
    """AttachedFile 목록을 Converse API content block 목록으로 변환한다.

    - 이미지 → ImageBlock 형식
    - 문서 → DocumentBlock 형식
    - 변환 실패한 파일은 건너뛰고 나머지만 반환

    Args:
        files: 변환할 AttachedFile 목록

    Returns:
        (blocks, failed_filenames) 튜플.
        blocks: 변환된 content block 목록.
        failed_filenames: 변환에 실패한 파일명 목록.
    """
    blocks: list[dict] = []
    failed: list[str] = []

    for file in files:
        try:
            block = _convert_file(file)
            blocks.append(block)
        except Exception:
            failed.append(file.filename)

    return blocks, failed


def _convert_file(file: AttachedFile) -> dict:
    """단일 파일을 Converse API content block으로 변환한다.

    Args:
        file: 변환할 AttachedFile

    Returns:
        ImageBlock 또는 DocumentBlock 딕셔너리

    Raises:
        ValueError: 알 수 없는 file_type인 경우
    """
    # 확장자 추출 (소문자, 점 제거)
    _, ext = os.path.splitext(file.filename)
    ext = ext[1:].lower()

    # jpg → jpeg 매핑 적용
    fmt = _FORMAT_MAP.get(ext, ext)

    if file.file_type == "image":
        return {
            "image": {
                "format": fmt,
                "source": {"bytes": file.data},
            }
        }

    if file.file_type == "document":
        # 문서 이름은 확장자를 제거한 파일명(stem)
        stem = os.path.splitext(file.filename)[0]
        return {
            "document": {
                "name": stem,
                "format": fmt,
                "source": {"bytes": file.data},
            }
        }

    raise ValueError(f"알 수 없는 파일 타입: {file.file_type}")
