"""채팅 서비스 - 대화 및 메시지 DB CRUD."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func

from wellbot.constants import CONVERSATION_LIMIT, KST
from wellbot.models.chat_message import ChtbMsgD
from wellbot.models.chat_summary import ChtbSmryD
from wellbot.services.database import get_session


def _verify_ownership(session, smry_id: str, emp_no: str) -> ChtbSmryD | None:
    """대화 소유권 검증. 소유자가 아니면 None 반환."""
    record = (
        session.query(ChtbSmryD)
        .filter(
            ChtbSmryD.chtb_tlk_smry_id == smry_id,
            ChtbSmryD.emp_no == emp_no,
        )
        .first()
    )
    return record


def list_conversations(emp_no: str) -> list[dict]:
    """사원의 대화 목록 조회 (최근 30개, 메시지 제외)."""
    with get_session() as session:
        rows = (
            session.query(ChtbSmryD)
            .filter(ChtbSmryD.emp_no == emp_no)
            .order_by(ChtbSmryD.rgst_dtm.desc())
            .limit(CONVERSATION_LIMIT)
            .all()
        )
        return [
            {
                "id": r.chtb_tlk_smry_id,
                "title": r.chtb_tlk_smry_ttl or "새 대화",
                "model_name": r.chtb_mdl_nm or "",
                "created_at": r.rgst_dtm.timestamp() if r.rgst_dtm else 0.0,
            }
            for r in rows
        ]


def get_conversation_messages(smry_id: str, emp_no: str) -> list[dict]:
    """대화의 메시지 목록 조회 (소유권 검증 포함).

    첨부파일은 GNB 팝오버에서 별도 표시하므로 메시지에 포함하지 않는다.
    """
    with get_session() as session:
        if not _verify_ownership(session, smry_id, emp_no):
            return []

        rows = (
            session.query(ChtbMsgD)
            .filter(
                ChtbMsgD.chtb_tlk_smry_id == smry_id,
                ChtbMsgD.msg_role_nm != "system",
            )
            .order_by(ChtbMsgD.chtb_tlk_seq.asc())
            .all()
        )

        return [
            {
                "role": r.msg_role_nm or "user",
                "content": r.chtb_msg_cntt or "",
                "timestamp": r.rgst_dtm.timestamp() if r.rgst_dtm else 0.0,
                "model_name": r.chtb_mdl_nm or "",
                "seq": int(r.chtb_tlk_seq) if r.chtb_tlk_seq is not None else 0,
                "msg_id": r.chtb_tlk_id or "",
            }
            for r in rows
        ]


def save_conversation(
    emp_no: str,
    conv_id: str,
    title: str,
    model_name: str = "",
) -> None:
    """대화 저장 (없으면 INSERT, 있으면 소유자 확인 후 UPDATE)."""
    now = datetime.now(KST)
    with get_session() as session:
        existing = _verify_ownership(session, conv_id, emp_no)
        if existing:
            existing.chtb_tlk_smry_ttl = title
            existing.chtb_mdl_nm = model_name or existing.chtb_mdl_nm
            existing.upd_dtm = now
            existing.uppr_id = emp_no[:20]
        else:
            record = ChtbSmryD(
                chtb_tlk_smry_id=conv_id,
                emp_no=emp_no,
                chtb_tlk_smry_ttl=title,
                chtb_mdl_nm=model_name or None,
                bkmr_yn="N",
                rgsr_id=emp_no[:20],
                rgst_dtm=now,
                uppr_id=emp_no[:20],
                upd_dtm=now,
            )
            session.add(record)


def update_conversation_title(smry_id: str, title: str, emp_no: str) -> None:
    """대화 제목 업데이트 (소유권 검증 포함)."""
    with get_session() as session:
        record = _verify_ownership(session, smry_id, emp_no)
        if record:
            record.chtb_tlk_smry_ttl = title
            record.upd_dtm = datetime.now(KST)
            record.uppr_id = emp_no[:20]


def get_next_seq(smry_id: str) -> int:
    """다음 메시지 순번 반환."""
    with get_session() as session:
        result = (
            session.query(func.max(ChtbMsgD.chtb_tlk_seq))
            .filter(ChtbMsgD.chtb_tlk_smry_id == smry_id)
            .scalar()
        )
        if result is None:
            return 1
        return int(result) + 1


def save_message(
    smry_id: str,
    seq: int,
    role: str,
    content: str,
    emp_no: str,
    model_name: str = "",
    provider: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    reply_time: float | None = None,
    msg_id: str | None = None,
) -> str:
    """메시지 DB 저장.

    Args:
        msg_id: 메시지 고유 ID. 미지정 시 UUID 자동 생성.

    Returns:
        저장된 메시지의 chtb_tlk_id (개별 메시지 고유 ID).
    """
    now = datetime.now(KST)
    total_tokens = input_tokens + output_tokens
    tlk_id = msg_id or uuid.uuid4().hex[:50]
    with get_session() as session:
        record = ChtbMsgD(
            chtb_tlk_smry_id=smry_id,
            chtb_tlk_id=tlk_id,
            chtb_tlk_seq=seq,
            msg_role_nm=role,
            chtb_msg_cntt=content,
            chtb_mdl_nm=model_name or None,
            chtb_offr_mdl_nm=provider or None,
            chtb_inpt_tokn_ecnt=input_tokens or None,
            chtb_otpt_tokn_ecnt=output_tokens or None,
            chtb_tot_tokn_ecnt=total_tokens or None,
            rply_time=Decimal(str(reply_time)) if reply_time else None,
            rgsr_id=emp_no[:20],
            rgst_dtm=now,
            uppr_id=emp_no[:20],
            upd_dtm=now,
        )
        session.add(record)
    return tlk_id


def delete_conversation(smry_id: str, emp_no: str) -> None:
    """대화 및 관련 메시지·첨부파일 삭제 (소유권 검증 포함)."""
    from wellbot.models.attachment import AtchFileM
    from wellbot.models.chat_message_attachment import ChtbMsgAtchFileD

    with get_session() as session:
        if not _verify_ownership(session, smry_id, emp_no):
            return

        # 대화에 속한 메시지의 chtb_tlk_id 목록 조회
        msg_ids = [
            row[0]
            for row in session.query(ChtbMsgD.chtb_tlk_id)
            .filter(ChtbMsgD.chtb_tlk_smry_id == smry_id)
            .all()
        ]

        if msg_ids:
            # 해당 메시지에 연결된 첨부파일 번호 조회
            file_nos = [
                row[0]
                for row in session.query(ChtbMsgAtchFileD.atch_file_no)
                .filter(ChtbMsgAtchFileD.chtb_tlk_id.in_(msg_ids))
                .all()
            ]

            # 첨부파일 매핑 삭제
            session.query(ChtbMsgAtchFileD).filter(
                ChtbMsgAtchFileD.chtb_tlk_id.in_(msg_ids)
            ).delete(synchronize_session="fetch")

            # 첨부파일 마스터 삭제
            if file_nos:
                session.query(AtchFileM).filter(
                    AtchFileM.atch_file_no.in_(file_nos)
                ).delete(synchronize_session="fetch")

        # 메시지 삭제
        session.query(ChtbMsgD).filter(
            ChtbMsgD.chtb_tlk_smry_id == smry_id
        ).delete()

        # 대화 요약 삭제
        session.query(ChtbSmryD).filter(
            ChtbSmryD.chtb_tlk_smry_id == smry_id
        ).delete()
