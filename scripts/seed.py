"""초기 부서 + 관리자 계정 시드 스크립트.

사용법: python scripts/seed.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime

import bcrypt
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

db_url = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST', '127.0.0.1')}:{os.getenv('DB_PORT', '3306')}"
    f"/{os.getenv('DB_NAME', 'wellbot')}"
)
engine = create_engine(db_url)

# --- 시드 데이터 (여기를 수정하세요) ---

DEPT_CD = "1"
DEPT_NM = "admingroup"
DD_CLBY_TOKN_ECNT = 9999999999  # NUMERIC(10) 최대값
MM_CLBY_TOKN_ECNT = 9999999999
PRMN_MDL_CNTT = '["*"]'  # 모든 모델 허용

EMP_NO = "admin"
USER_NM = "admin"
PASSWORD = "dlatl12!@"
USER_ROLE_NM = "super-admin"
ACNT_STS_NM = "active"

# --- 실행 ---

now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
salt = bcrypt.gensalt()
ecr_pwd = bcrypt.hashpw(PASSWORD.encode("utf-8"), salt).decode("utf-8")

with Session(engine) as session:
    # 부서 삽입
    exists = session.execute(
        text("SELECT 1 FROM DEPT_M WHERE DEPT_CD = :cd"), {"cd": DEPT_CD}
    ).first()
    if not exists:
        session.execute(
            text("""
                INSERT INTO DEPT_M (DEPT_CD, DEPT_NM, DD_CLBY_TOKN_ECNT, MM_CLBY_TOKN_ECNT, PRMN_MDL_CNTT,
                                    RGST_DTM, RGSR_ID, UPD_DTM, UPPR_ID)
                VALUES (:dept_cd, :dept_nm, :dd, :mm, :prmn, :now, :rid, :now, :uid)
            """),
            {
                "dept_cd": DEPT_CD, "dept_nm": DEPT_NM,
                "dd": DD_CLBY_TOKN_ECNT, "mm": MM_CLBY_TOKN_ECNT, "prmn": PRMN_MDL_CNTT,
                "now": now, "rid": "SYSTEM", "uid": "SYSTEM",
            },
        )
        print(f"[OK] 부서 생성: {DEPT_CD} ({DEPT_NM})")
    else:
        print(f"[SKIP] 부서 이미 존재: {DEPT_CD}")

    # 관리자 계정 삽입
    exists = session.execute(
        text("SELECT 1 FROM EMP_M WHERE EMP_NO = :no"), {"no": EMP_NO}
    ).first()
    if not exists:
        session.execute(
            text("""
                INSERT INTO EMP_M (EMP_NO, USER_NM, ECR_PWD, USER_ROLE_NM,
                                   PSTN_DEPT_CD, ACNT_STS_NM,
                                   RGST_DTM, RGSR_ID, UPD_DTM, UPPR_ID)
                VALUES (:emp_no, :user_nm, :pwd, :role,
                        :dept, :sts,
                        :now, :rid, :now, :uid)
            """),
            {
                "emp_no": EMP_NO, "user_nm": USER_NM,
                "pwd": ecr_pwd, "role": USER_ROLE_NM,
                "dept": DEPT_CD, "sts": ACNT_STS_NM,
                "now": now, "rid": "SYSTEM", "uid": "SYSTEM",
            },
        )
        print(f"[OK] 관리자 생성: {EMP_NO} ({USER_NM})")
    else:
        print(f"[SKIP] 관리자 이미 존재: {EMP_NO}")

    session.commit()

print("\nSeed 완료.")
