"""채팅 서비스 - 대화 및 메시지 DB CRUD."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func

from wellbot.constants import CONVERSATION_LIMIT, KST
from wellbot.models.attachment import AtchFileM
from wellbot.models.chat_message import ChtbMsgD
from wellbot.models.chat_message_attachment import ChtbMsgAtchFileD
from wellbot.models.chat_summary import ChtbSmryD
from wellbot.services import file_parser
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

    user 메시지 중 첫 번째(=가장 낮은 seq) 에 대화 전체 첨부파일
    목록을 붙여 반환한다.

    Note: 현재 스키마에는 "메시지 ↔ 파일" 의 직접 매핑이 없으므로
    (chtb_msg_atch_file_d 는 대화 단위 매핑), 대화 전체의 첨부파일을
    첫 user 메시지 버블 아래에 카드로 표시하는 정책을 채택한다.
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

        # 대화 첨부파일 일괄 조회 (첫 user 메시지에만 바인딩)
        att_rows = (
            session.query(AtchFileM)
            .join(
                ChtbMsgAtchFileD,
                ChtbMsgAtchFileD.atch_file_no == AtchFileM.atch_file_no,
            )
            .filter(ChtbMsgAtchFileD.chtb_tlk_id == smry_id)
            .order_by(AtchFileM.atch_file_no.asc())
            .all()
        )
        attachments = [
            {
                "file_no": int(a.atch_file_no),
                "name": a.atch_file_nm or "",
                "mime": file_parser.guess_mime(a.atch_file_nm or ""),
                "size_bytes": 0,
                "token_count": int(a.atch_file_tokn_ecnt or 0),
                "status": (
                    "ready"
                    if a.atch_file_tokn_ecnt is not None
                    else "processing"
                ),
            }
            for a in att_rows
        ]

        results: list[dict] = []
        first_user_seen = False
        for r in rows:
            role = r.msg_role_nm or "user"
            item_attachments: list[dict] = []
            if role == "user" and not first_user_seen and attachments:
                item_attachments = attachments
                first_user_seen = True

            results.append(
                {
                    "role": role,
                    "content": r.chtb_msg_cntt or "",
                    "timestamp": r.rgst_dtm.timestamp() if r.rgst_dtm else 0.0,
                    "model_name": r.chtb_mdl_nm or "",
                    "seq": int(r.chtb_tlk_seq) if r.chtb_tlk_seq is not None else 0,
                    "attachments": item_attachments,
                }
            )
        return results


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
) -> None:
    """메시지 DB 저장."""
    now = datetime.now(KST)
    total_tokens = input_tokens + output_tokens
    with get_session() as session:
        record = ChtbMsgD(
            chtb_tlk_smry_id=smry_id,
            chtb_tlk_id=smry_id,
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


def delete_conversation(smry_id: str, emp_no: str) -> None:
    """대화 및 관련 메시지 삭제 (소유권 검증 포함)."""
    with get_session() as session:
        if not _verify_ownership(session, smry_id, emp_no):
            return
        session.query(ChtbMsgD).filter(
            ChtbMsgD.chtb_tlk_smry_id == smry_id
        ).delete()
        session.query(ChtbSmryD).filter(
            ChtbSmryD.chtb_tlk_smry_id == smry_id
        ).delete()
