"""첨부파일 서비스.

업로드 파이프라인:
    1. register_attachment(): 파일 업로드 직후 S3 원본 저장 + DB 레코드 생성
    2. process_attachment(): 파싱 → 청킹 → 임베딩 → S3 파생물 저장

`atch_file_no` 는 BigInteger PK 이며 DB AUTO_INCREMENT 로 자동 발급.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from wellbot.models.attachment import AtchFileM
from wellbot.models.chat_message_attachment import ChtbMsgAtchFileD
from wellbot.constants import KST
from wellbot.services import chunker, embedding_service, file_parser, storage_service
from wellbot.services.database import get_session

log = logging.getLogger(__name__)


# ── 데이터 전송 객체 ──


@dataclass(frozen=True)
class AttachmentRecord:
    """첨부파일 레코드 (조회 결과)."""

    file_no: int
    file_name: str
    s3_prefix: str
    token_count: int | None  # None = 처리 중, 0 이상 = 처리 완료
    mime: str


# ── 원본 파일 S3 업로드 + DB 등록 ──


def register_attachment(
    emp_no: str,
    smry_id: str,
    filename: str,
    content_type: str,
    file_path: Path,
) -> int:
    """업로드된 원본 파일을 S3 에 저장하고 DB 에 등록한다.

    Args:
        emp_no: 업로드한 사원 번호.
        smry_id: 대화 ID.
        filename: 원본 파일명 (확장자 포함).
        content_type: MIME 타입.
        file_path: 서버에 임시 저장된 파일 경로.

    Returns:
        생성된 atch_file_no.
    """
    now = datetime.now(KST)

    with get_session() as session:
        # atch_file_m INSERT (file_no 는 DB AUTO_INCREMENT)
        record = AtchFileM(
            atch_file_nm=filename[:300],
            atch_file_url_addr="",  # S3 업로드 후 갱신
            atch_file_tokn_ecnt=None,  # 파싱 후 업데이트
            rgst_dtm=now,
            rgsr_id=emp_no[:20],
            upd_dtm=now,
            uppr_id=emp_no[:20],
        )
        session.add(record)
        session.flush()  # DB 에서 auto-increment PK 발급
        file_no = record.atch_file_no

        # S3 prefix 생성 + 원본 업로드
        s3_prefix = storage_service.build_prefix(emp_no, smry_id, file_no)
        ext = Path(filename).suffix.lower()
        original_key = f"{s3_prefix}original{ext}"
        with open(file_path, "rb") as f:
            storage_service.upload_streaming(f, original_key, content_type)

        # S3 prefix 를 DB 에 반영
        record.atch_file_url_addr = s3_prefix[:500]

        # chtb_msg_atch_file_d INSERT (대화 매핑)
        mapping = ChtbMsgAtchFileD(
            chtb_tlk_id=smry_id,
            atch_file_no=file_no,
            rgst_dtm=now,
            rgsr_id=emp_no[:20],
            upd_dtm=now,
            uppr_id=emp_no[:20],
        )
        session.add(mapping)

    return file_no


# ── 파싱 + 청킹 + 임베딩 + S3 파생물 저장 ──


def process_attachment(file_no: int, emp_no: str) -> bool:
    """첨부파일을 파싱하고 파생물(청크/인덱스)을 S3 에 저장한다.

    이미지 파일은 파싱·임베딩을 건너뛰고 토큰 수만 0 으로 기록한다
    (이미지는 Bedrock Converse vision block 으로 직접 전달됨).

    Args:
        file_no: atch_file_m PK.
        emp_no: 업데이트 주체.

    Returns:
        성공 여부.
    """
    # 1. DB 에서 prefix 와 파일명 조회
    with get_session() as session:
        record = session.query(AtchFileM).get(file_no)
        if not record:
            log.warning("process_attachment: file_no=%s 레코드 없음", file_no)
            return False
        s3_prefix = record.atch_file_url_addr or ""
        filename = record.atch_file_nm or f"file_{file_no}"

    if not s3_prefix:
        log.error("process_attachment: file_no=%s S3 prefix 비어있음", file_no)
        return False

    ext = Path(filename).suffix.lower()
    original_key = f"{s3_prefix}original{ext}"

    # 2. 이미지 파일은 파싱 건너뛰기
    if file_parser.is_image(filename):
        _update_token_count(file_no, emp_no, 0)
        log.info("process_attachment: 이미지 파일 스킵 (file_no=%s)", file_no)
        return True

    # 3. S3 에서 원본 다운로드 (임시 파일)
    tmp_dir = Path(tempfile.gettempdir()) / "wellbot_attachment_process"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{file_no}_{Path(filename).name}"
    try:
        storage_service.download_to_file(original_key, tmp_path)

        # 4. 파싱
        parser = file_parser.get_parser()
        parsed = parser.parse(tmp_path)

        if not parsed.text.strip():
            log.warning("process_attachment: file_no=%s 파싱 결과 비어있음", file_no)
            _update_token_count(file_no, emp_no, 0)
            return True  # 파싱은 "성공" 했으나 내용 없음

        # 5. 청킹
        chunks = chunker.chunk_text(parsed.text)
        total_tokens = sum(c.token_count for c in chunks)

        # 6. 임베딩
        embeddings = embedding_service.embed_texts([c.text for c in chunks])

        # 7. FAISS 인덱스 빌드 + 직렬화
        index = embedding_service.build_index(embeddings)
        index_bytes = embedding_service.serialize_index(index)

        # 8. 파생물 S3 업로드
        chunks_key = f"{s3_prefix}chunks.jsonl"
        index_key = f"{s3_prefix}index.faiss"
        storage_service.upload_bytes(
            chunker.chunks_to_jsonl(chunks),
            chunks_key,
            content_type="application/x-jsonlines",
        )
        storage_service.upload_bytes(
            index_bytes,
            index_key,
            content_type="application/octet-stream",
        )

        # 9. 토큰 수 업데이트
        _update_token_count(file_no, emp_no, total_tokens)

        # 10. 캐시 무효화 (다음 조회 시 재로드)
        smry_id = _smry_id_from_record(file_no)
        if smry_id:
            embedding_service.get_cache().invalidate(smry_id)

        log.info(
            "process_attachment 완료: file_no=%s chunks=%d tokens=%d",
            file_no,
            len(chunks),
            total_tokens,
        )
        return True

    except Exception as exc:
        log.exception("process_attachment 실패: file_no=%s err=%s", file_no, exc)
        return False
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _update_token_count(file_no: int, emp_no: str, total_tokens: int) -> None:
    """atch_file_m.atch_file_tokn_ecnt 갱신."""
    now = datetime.now(KST)
    with get_session() as session:
        record = session.query(AtchFileM).get(file_no)
        if not record:
            return
        record.atch_file_tokn_ecnt = total_tokens
        record.upd_dtm = now
        record.uppr_id = emp_no[:20]


def _smry_id_from_record(file_no: int) -> str:
    """DB 매핑 테이블에서 smry_id 를 조회한다.

    S3 prefix 파싱은 KEY_PREFIX 길이에 따라 인덱스가 달라지므로
    DB 를 정본(source of truth)으로 사용한다.
    """
    with get_session() as session:
        row = (
            session.query(ChtbMsgAtchFileD.chtb_tlk_id)
            .filter(ChtbMsgAtchFileD.atch_file_no == file_no)
            .first()
        )
        return row[0] if row else ""


# ── 조회 ──


def get_conversation_attachments(smry_id: str) -> list[AttachmentRecord]:
    """대화에 연결된 모든 첨부파일 목록 반환."""
    with get_session() as session:
        rows = (
            session.query(AtchFileM)
            .join(
                ChtbMsgAtchFileD,
                ChtbMsgAtchFileD.atch_file_no == AtchFileM.atch_file_no,
            )
            .filter(ChtbMsgAtchFileD.chtb_tlk_id == smry_id)
            .order_by(AtchFileM.atch_file_no.asc())
            .all()
        )
        return [
            AttachmentRecord(
                file_no=int(r.atch_file_no),
                file_name=r.atch_file_nm or "",
                s3_prefix=r.atch_file_url_addr or "",
                token_count=(
                    int(r.atch_file_tokn_ecnt)
                    if r.atch_file_tokn_ecnt is not None
                    else None
                ),
                mime=file_parser.guess_mime(r.atch_file_nm or ""),
            )
            for r in rows
        ]


def get_attachment(file_no: int) -> AttachmentRecord | None:
    """단일 첨부파일 조회."""
    with get_session() as session:
        record = session.query(AtchFileM).get(file_no)
        if not record:
            return None
        return AttachmentRecord(
            file_no=int(record.atch_file_no),
            file_name=record.atch_file_nm or "",
            s3_prefix=record.atch_file_url_addr or "",
            token_count=(
                int(record.atch_file_tokn_ecnt)
                if record.atch_file_tokn_ecnt is not None
                else None
            ),
            mime=file_parser.guess_mime(record.atch_file_nm or ""),
        )


def get_download_url(file_no: int) -> str | None:
    """첨부파일 다운로드용 presigned URL 생성."""
    att = get_attachment(file_no)
    if not att or not att.s3_prefix:
        return None
    ext = Path(att.file_name).suffix.lower()
    s3_key = f"{att.s3_prefix}original{ext}"
    return storage_service.get_presigned_url(
        s3_key,
        download_filename=att.file_name,
    )


def download_original_bytes(file_no: int) -> bytes | None:
    """원본 파일 바이너리를 S3 에서 다운로드한다.

    이미지 첨부를 Bedrock Converse `image` block 으로 전달하기 위해 사용.
    """
    att = get_attachment(file_no)
    if not att or not att.s3_prefix:
        return None
    ext = Path(att.file_name).suffix.lower()
    s3_key = f"{att.s3_prefix}original{ext}"
    try:
        return storage_service.download_bytes(s3_key)
    except Exception as exc:
        log.warning("원본 다운로드 실패 (file_no=%s): %s", file_no, exc)
        return None


def verify_ownership(file_no: int, emp_no: str) -> bool:
    """사원이 해당 파일의 대화 소유자인지 확인."""
    from wellbot.models.chat_summary import ChtbSmryD

    with get_session() as session:
        row = (
            session.query(ChtbSmryD)
            .join(
                ChtbMsgAtchFileD,
                ChtbMsgAtchFileD.chtb_tlk_id == ChtbSmryD.chtb_tlk_smry_id,
            )
            .filter(
                ChtbMsgAtchFileD.atch_file_no == file_no,
                ChtbSmryD.emp_no == emp_no,
            )
            .first()
        )
        return row is not None


def delete_attachment(file_no: int, emp_no: str) -> bool:
    """첨부파일 삭제 (DB + S3). 소유권 확인 포함."""
    if not verify_ownership(file_no, emp_no):
        return False

    att = get_attachment(file_no)
    if not att:
        return False

    # S3 파일들 삭제
    if att.s3_prefix:
        try:
            storage_service.delete_prefix(att.s3_prefix)
        except Exception as exc:
            log.warning("S3 삭제 실패 (file_no=%s): %s", file_no, exc)

    # 캐시 무효화 (DB 삭제 전에 smry_id 조회)
    smry_id = _smry_id_from_record(file_no)

    # DB 레코드 삭제
    with get_session() as session:
        session.query(ChtbMsgAtchFileD).filter(
            ChtbMsgAtchFileD.atch_file_no == file_no
        ).delete()
        session.query(AtchFileM).filter(AtchFileM.atch_file_no == file_no).delete()

    if smry_id:
        embedding_service.get_cache().invalidate(smry_id)
    return True


def count_conversation_attachments(smry_id: str) -> tuple[int, int]:
    """대화 내 첨부파일 개수 및 총 토큰 수.

    Returns:
        (file_count, total_tokens)
    """
    with get_session() as session:
        rows = (
            session.query(AtchFileM.atch_file_tokn_ecnt)
            .join(
                ChtbMsgAtchFileD,
                ChtbMsgAtchFileD.atch_file_no == AtchFileM.atch_file_no,
            )
            .filter(ChtbMsgAtchFileD.chtb_tlk_id == smry_id)
            .all()
        )
        file_count = len(rows)
        total_tokens = sum(int(r[0] or 0) for r in rows)
        return file_count, total_tokens
