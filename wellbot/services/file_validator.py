"""파일 검증 모듈.

업로드된 파일의 확장자, 크기, 개수를 검증하는 순수 함수 모듈.
ChatState와 분리하여 테스트 용이성을 확보한다.
"""

import os

# 지원 확장자 집합
IMAGE_EXTENSIONS: set[str] = {"png", "jpeg", "jpg", "gif", "webp"}
DOCUMENT_EXTENSIONS: set[str] = {"pdf", "csv", "doc", "docx", "xls", "xlsx", "html", "txt", "md"}

# 파일 크기 제한 (바이트)
IMAGE_MAX_SIZE: int = 3_932_160    # 3.75 MB
DOCUMENT_MAX_SIZE: int = 4_718_592  # 4.5 MB

# 파일 개수 제한
IMAGE_MAX_COUNT: int = 20
DOCUMENT_MAX_COUNT: int = 5

def classify_file(filename: str) -> str:
    """파일 확장자를 기반으로 파일 타입을 분류한다.

    Args:
        filename: 원본 파일명 (예: "photo.png", "report.pdf")

    Returns:
        'image' 또는 'document'

    Raises:
        ValueError: 지원되지 않는 확장자인 경우
    """
    ext = _extract_extension(filename)

    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in DOCUMENT_EXTENSIONS:
        return "document"

    raise ValueError(
        "지원되지 않는 파일 형식입니다. "
        "지원 형식: png, jpeg, jpg, gif, webp, pdf, csv, doc, docx, xls, xlsx, html, txt, md"
    )


def validate_file(
    filename: str,
    file_size: int,
    current_image_count: int,
    current_document_count: int,
) -> None:
    """파일의 확장자, 크기, 개수를 검증한다.

    검증 순서: 확장자 → 크기 → 개수

    Args:
        filename: 원본 파일명
        file_size: 파일 크기 (바이트)
        current_image_count: 현재 첨부된 이미지 파일 수
        current_document_count: 현재 첨부된 문서 파일 수

    Raises:
        ValueError: 검증 실패 시 해당 에러 메시지와 함께 발생
    """
    # 1. 확장자 검증 (classify_file이 ValueError를 발생시킴)
    file_type = classify_file(filename)

    # 2. 크기 검증
    if file_type == "image" and file_size > IMAGE_MAX_SIZE:
        size_mb = round(file_size / (1024 * 1024), 2)
        raise ValueError(
            f"이미지 파일은 최대 3.75MB까지 업로드할 수 있습니다. ({filename}: {size_mb}MB)"
        )

    if file_type == "document" and file_size > DOCUMENT_MAX_SIZE:
        size_mb = round(file_size / (1024 * 1024), 2)
        raise ValueError(
            f"문서 파일은 최대 4.5MB까지 업로드할 수 있습니다. ({filename}: {size_mb}MB)"
        )

    # 3. 개수 검증
    if file_type == "image" and current_image_count >= IMAGE_MAX_COUNT:
        raise ValueError("이미지 파일은 최대 20개까지 첨부할 수 있습니다.")

    if file_type == "document" and current_document_count >= DOCUMENT_MAX_COUNT:
        raise ValueError("문서 파일은 최대 5개까지 첨부할 수 있습니다.")


def _extract_extension(filename: str) -> str:
    """파일명에서 확장자를 추출한다 (소문자 변환).

    Args:
        filename: 원본 파일명

    Returns:
        소문자 확장자 문자열 (점 제외)

    Raises:
        ValueError: 확장자가 없는 경우
    """
    _, ext = os.path.splitext(filename)
    if not ext:
        raise ValueError(
            "지원되지 않는 파일 형식입니다. "
            "지원 형식: png, jpeg, jpg, gif, webp, pdf, csv, doc, docx, xls, xlsx, html, txt, md"
        )
    # 점(.) 제거 후 소문자 변환
    return ext[1:].lower()
