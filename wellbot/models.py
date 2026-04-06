"""WellBot 데이터베이스 모델 정의.

실제 MySQL 스키마(docs/database-architecture.md)를 기반으로 정의.
rx.ModelRegistry.register + sqlmodel.SQLModel 방식 사용 (Reflex 0.8.15+ 권장).
"""

from datetime import datetime
from typing import Optional

import reflex as rx
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT
import sqlmodel
from sqlmodel import Field


# ---------------------------------------------------------------------------
# 공통 감사(audit) 컬럼 Mixin
# ---------------------------------------------------------------------------
class AuditMixin(sqlmodel.SQLModel):
    """모든 테이블 공통 감사 컬럼 (RGST_DTM, RGST_ID, UPD_DTM, UPPR_ID)."""

    rgst_dtm: datetime = Field(
        sa_type=sa.DateTime,
        sa_column_kwargs={"name": "RGST_DTM", "nullable": False},
    )
    rgst_id: str = Field(
        sa_type=sa.String(20),
        sa_column_kwargs={"name": "RGST_ID", "nullable": False},
    )
    upd_dtm: datetime = Field(
        sa_type=sa.DateTime,
        sa_column_kwargs={"name": "UPD_DTM", "nullable": False},
    )
    uppr_id: str = Field(
        sa_type=sa.String(20),
        sa_column_kwargs={"name": "UPPR_ID", "nullable": False},
    )


# ---------------------------------------------------------------------------
# 1. 부서마스터 (DEPT_M)
# ---------------------------------------------------------------------------
@rx.ModelRegistry.register
class DeptM(AuditMixin, table=True):
    """부서별 일일/월간 토큰 쿼터 및 허용 모델 관리."""

    __tablename__ = "DEPT_M"

    dept_cd: str = Field(
        sa_column=sa.Column("DEPT_CD", sa.String(8), primary_key=True)
    )
    dept_nm: str = Field(
        sa_column=sa.Column("DEPT_NM", sa.String(50), unique=True)
    )
    dd_tokn_ecnt: Optional[int] = Field(
        default=None,
        sa_column=sa.Column("DD_TOKN_ECNT", sa.Numeric(10)),
    )
    mm_tokn_ecnt: Optional[int] = Field(
        default=None,
        sa_column=sa.Column("MM_TOKN_ECNT", sa.Numeric(10)),
    )
    aces_mdl_cntt: Optional[dict] = Field(
        default=None,
        sa_column=sa.Column("ACES_MDL_CNTT", sa.JSON),
    )


# ---------------------------------------------------------------------------
# 2. 사원마스터 (EMP_M)
# ---------------------------------------------------------------------------
@rx.ModelRegistry.register
class EmpM(AuditMixin, table=True):
    """사용자 계정 (역할, 상태, 잠금 관리)."""

    __tablename__ = "EMP_M"

    emp_no: str = Field(
        sa_column=sa.Column("EMP_NO", sa.String(15), primary_key=True)
    )
    user_nm: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("USER_NM", sa.String(50)),
    )
    eml_addr: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("EML_ADDR", sa.String(100), unique=True),
    )
    ecr_pwd: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("ECR_PWD", sa.String(255)),
    )
    user_role_nm: str = Field(
        sa_column=sa.Column("USER_ROLE_NM", sa.String(50), nullable=False)
    )
    pstn_dept_cd: str = Field(
        sa_column=sa.Column(
            "PSTN_DEPT_CD",
            sa.String(8),
            sa.ForeignKey("DEPT_M.DEPT_CD"),
            nullable=False,
        )
    )
    acnt_sts_nm: str = Field(
        sa_column=sa.Column("ACNT_STS_NM", sa.String(50), nullable=False)
    )
    lgn_scs_dtm: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column("LGN_SCS_DTM", sa.DateTime),
    )
    lgn_flr_tscnt: int = Field(
        default=0,
        sa_column=sa.Column("LGN_FLR_TSCNT", sa.Numeric(5), nullable=False),
    )
    lock_dsbn_dtm: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column("LOCK_DSBN_DTM", sa.DateTime),
    )
    user_uuid: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("USER_UUID", sa.String(36)),
    )


# ---------------------------------------------------------------------------
# 3. 인증토큰내역 (CRTF_TOKN_N)
# ---------------------------------------------------------------------------
@rx.ModelRegistry.register
class CrtfToknN(AuditMixin, table=True):
    """사용자별 인증 토큰 관리 (JWT 등)."""

    __tablename__ = "CRTF_TOKN_N"
    __table_args__ = (
        sa.PrimaryKeyConstraint("EMP_NO", "CRTF_TOKN_ID"),
    )

    emp_no: str = Field(
        sa_column=sa.Column("EMP_NO", sa.String(15))
    )
    crtf_tokn_id: str = Field(
        sa_column=sa.Column("CRTF_TOKN_ID", sa.String(50))
    )
    crtf_tokn_ecr_cntt: str = Field(
        sa_column=sa.Column("CRTF_TOKN_ECR_CNTT", sa.String(300), nullable=False)
    )
    diss_yn: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("DISS_YN", sa.String(1)),
    )
    trtn_dtm: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column("TRTN_DTM", sa.DateTime),
    )
    diss_dtm: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column("DISS_DTM", sa.DateTime),
    )


# ---------------------------------------------------------------------------
# 4. 챗봇요약상세 (CHTB_SMRY_D)
# ---------------------------------------------------------------------------
@rx.ModelRegistry.register
class ChtbSmryD(AuditMixin, table=True):
    """대화 세션 단위 정보 (사이드바 대화 이력)."""

    __tablename__ = "CHTB_SMRY_D"

    chtb_tlk_smry_id: str = Field(
        sa_column=sa.Column("CHTB_TLK_SMRY_ID", sa.String(50), primary_key=True)
    )
    emp_no: str = Field(
        sa_column=sa.Column("EMP_NO", sa.String(20), nullable=False)
    )
    chtb_tlk_smry_ttl: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("CHTB_TLK_SMRY_TTL", sa.String(255)),
    )
    chtb_mdl_nm: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("CHTB_MDL_NM", sa.String(100)),
    )
    bkmr_yn: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("BKMR_YN", sa.String(1)),
    )


# ---------------------------------------------------------------------------
# 5. 챗봇메시지상세 (CHTB_MSG_D)
# ---------------------------------------------------------------------------
@rx.ModelRegistry.register
class ChtbMsgD(AuditMixin, table=True):
    """개별 메시지 (토큰 수, 응답시간, 첨부파일 참조)."""

    __tablename__ = "CHTB_MSG_D"
    __table_args__ = (
        sa.PrimaryKeyConstraint("CHTB_TLK_SMRY_ID", "CHTB_TLK_ID", "CHTB_TLK_SEQ"),
    )

    chtb_tlk_smry_id: str = Field(
        sa_column=sa.Column("CHTB_TLK_SMRY_ID", sa.String(50))
    )
    chtb_tlk_id: str = Field(
        sa_column=sa.Column("CHTB_TLK_ID", sa.String(50))
    )
    chtb_tlk_seq: int = Field(
        sa_column=sa.Column("CHTB_TLK_SEQ", sa.Numeric(10))
    )
    agnt_id: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("AGNT_ID", sa.String(50)),
    )
    msg_role_nm: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("MSG_ROLE_NM", sa.String(50)),
    )
    chtb_msg_cntt: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("CHTB_MSG_CNTT", sa.Text().with_variant(MEDIUMTEXT, "mysql")),
    )
    chtb_mdl_nm: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("CHTB_MDL_NM", sa.String(100)),
    )
    chtb_offr_mdl_nm: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("CHTB_OFFR_MDL_NM", sa.String(50)),
    )
    chtb_input_tokn_ecnt: Optional[int] = Field(
        default=None,
        sa_column=sa.Column("CHTB_INPUT_TOKN_ECNT", sa.Numeric(10)),
    )
    chtb_output_tokn_ecnt: Optional[int] = Field(
        default=None,
        sa_column=sa.Column("CHTB_OUTPUT_TOKN_ECNT", sa.Numeric(10)),
    )
    chtb_tot_tokn_ecnt: Optional[int] = Field(
        default=None,
        sa_column=sa.Column("CHTB_TOT_TOKN_ECNT", sa.Numeric(10)),
    )
    rply_time: Optional[float] = Field(
        default=None,
        sa_column=sa.Column("RPLY_TIME", sa.Numeric(5, 2)),
    )
    atch_file_no: Optional[int] = Field(
        default=None,
        sa_column=sa.Column("ATCH_FILE_NO", sa.BigInteger),
    )


# ---------------------------------------------------------------------------
# 6. 첨부파일마스터 (ATCH_FILE_M)
# ---------------------------------------------------------------------------
@rx.ModelRegistry.register
class AtchFileM(AuditMixin, table=True):
    """첨부파일 메타데이터 (S3 경로, 토큰 수)."""

    __tablename__ = "ATCH_FILE_M"
    __table_args__ = (
        sa.PrimaryKeyConstraint("CHTB_TLK_ID", "ATCH_FILE_NO"),
    )

    chtb_tlk_id: str = Field(
        sa_column=sa.Column("CHTB_TLK_ID", sa.String(50))
    )
    atch_file_no: int = Field(
        sa_column=sa.Column("ATCH_FILE_NO", sa.BigInteger)
    )
    atch_file_nm: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("ATCH_FILE_NM", sa.String(255)),
    )
    atch_file_url_addr: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("ATCH_FILE_URL_ADDR", sa.String(500)),
    )
    atch_tokn_ecnt: Optional[int] = Field(
        default=None,
        sa_column=sa.Column("ATCH_TOKN_ECNT", sa.Numeric(10)),
    )


# ---------------------------------------------------------------------------
# 7. 에이전트마스터 (AGENT_M)
# ---------------------------------------------------------------------------
@rx.ModelRegistry.register
class AgentM(AuditMixin, table=True):
    """지원 Agent 목록 (프레임워크, 경로, 설명)."""

    __tablename__ = "AGENT_M"
    __table_args__ = (
        sa.PrimaryKeyConstraint("AGENT_ID", "AGENT_SEQ"),
    )

    agent_id: str = Field(
        sa_column=sa.Column("AGENT_ID", sa.String(50))
    )
    agent_seq: int = Field(
        sa_column=sa.Column("AGENT_SEQ", sa.Numeric(10))
    )
    agent_nm: str = Field(
        sa_column=sa.Column("AGENT_NM", sa.String(100), nullable=False)
    )
    agent_frwk_nm: str = Field(
        sa_column=sa.Column("AGENT_FRWK_NM", sa.String(100), nullable=False)
    )
    agent_path_addr: str = Field(
        sa_column=sa.Column("AGENT_PATH_ADDR", sa.String(300), nullable=False)
    )
    agent_dscr_cntt: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("AGENT_DSCR_CNTT", sa.Text().with_variant(MEDIUMTEXT, "mysql")),
    )
    use_yn: str = Field(
        sa_column=sa.Column("USE_YN", sa.String(1), nullable=False)
    )


# ---------------------------------------------------------------------------
# 8. 에이전트메모리사용내역 (AGENT_MEM_USE_N)
# ---------------------------------------------------------------------------
@rx.ModelRegistry.register
class AgentMemUseN(AuditMixin, table=True):
    """Agent별 메모리 사용 이력."""

    __tablename__ = "AGENT_MEM_USE_N"
    __table_args__ = (
        sa.PrimaryKeyConstraint("AGENT_ID", "AGENT_SEQ", "EMP_NO"),
    )

    agent_id: str = Field(
        sa_column=sa.Column("AGENT_ID", sa.String(100))
    )
    agent_seq: int = Field(
        sa_column=sa.Column("AGENT_SEQ", sa.Numeric(10))
    )
    emp_no: str = Field(
        sa_column=sa.Column("EMP_NO", sa.String(100))
    )
    agent_mem_path_addr: Optional[str] = Field(
        default=None,
        sa_column=sa.Column("AGENT_MEM_PATH_ADDR", sa.String(300)),
    )
    agent_type_dscr_cntt: str = Field(
        sa_column=sa.Column("AGENT_TYPE_DSCR_CNTT", sa.Text().with_variant(MEDIUMTEXT, "mysql"), nullable=False)
    )
    use_yn: str = Field(
        sa_column=sa.Column("USE_YN", sa.String(1), nullable=False)
    )
    last_sync_dtm: Optional[datetime] = Field(
        default=None,
        sa_column=sa.Column("LAST_SYNC_DTM", sa.DateTime),
    )
