# WellBot 데이터베이스 아키텍처

## 개요

WellBot은 사용자 관리, 인증, 대화 이력 등의 데이터를 MySQL 데이터베이스에 저장하며,
Reflex ORM을 통해 간접적으로 DB에 접근하는 구조를 채택하고 있다.

## 기술 스택

| 구분 | 기술 | 역할 |
|------|------|------|
| DBMS | MySQL | 실제 데이터 저장소 |
| 동기 드라이버 | PyMySQL | SQLAlchemy가 MySQL과 동기 통신 시 사용 |
| 비동기 드라이버 | aiomysql | 비동기 DB 접근 시 사용 |
| ORM | SQLModel | Pydantic + SQLAlchemy 기반 ORM |
| 프레임워크 ORM | Reflex `rx.Model` | SQLModel을 래핑한 Reflex 전용 모델 클래스 |
| SSL/암호화 | cryptography | MySQL SSL 연결 등 암호화 처리 |

## 아키텍처 흐름

```
사용자 UI (Reflex Frontend)
    ↕
State 클래스 (rx.State)
    ↕  rx.session()
Reflex ORM (rx.Model → SQLModel → SQLAlchemy)
    ↕  PyMySQL / aiomysql
MySQL 서버
```

## DB 연결 설정

### rxconfig.py

`rxconfig.py`에서 `db_url`을 지정하여 MySQL 연결을 구성한다.
현재는 `db_url`이 미설정 상태이므로 Reflex 기본값인 SQLite로 동작한다.

```python
# MySQL 연결 예시
import reflex as rx

config = rx.Config(
    app_name="wellbot",
    db_url="mysql+pymysql://<user>:<password>@<host>:<port>/<database>",
)
```

### 커넥션 풀 (Connection Pool)

- SQLAlchemy가 내부적으로 커넥션 풀을 관리
- 앱 시작 시 DB 연결을 맺어두고, 이후 요청마다 풀에서 커넥션을 재사용
- 매 요청마다 새로 연결하지 않으므로 오버헤드가 적음

## 모델 정의

### 현재 정의된 모델

`wellbot/models.py`에서 `rx.Model`을 상속하여 테이블을 정의한다.

```python
import reflex as rx

class User(rx.Model, table=True):
    __tablename__ = "wellbot_user"
    username: str
    password_hash: str
    is_admin: bool = False
```

- `rx.Model`은 내부적으로 `SQLModel`을 상속
- `table=True` 지정 시 실제 DB 테이블로 매핑
- `__tablename__`으로 테이블명을 명시적으로 지정

## DB 접근 패턴

### 세션 사용법

Reflex에서는 `rx.session()` 컨텍스트 매니저를 통해 DB 세션을 획득한다.

```python
# 조회
with rx.session() as session:
    user = session.query(User).filter(User.username == username).first()

# 삽입
with rx.session() as session:
    session.add(new_user)
    session.commit()

# 삭제
with rx.session() as session:
    session.delete(user)
    session.commit()

# 수정
with rx.session() as session:
    user.is_admin = not user.is_admin
    session.add(user)
    session.commit()
```

### DB 접근이 발생하는 시점

| 시점 | 위치 | 설명 |
|------|------|------|
| 로그인 | `state/auth.py` → `login()` | 사용자 조회 및 비밀번호 검증 |
| 사용자 목록 조회 | `state/admin.py` → `load_users()` | 관리자 페이지에서 전체 사용자 로드 |
| 사용자 추가 | `state/admin.py` → `add_user()` | 중복 확인 후 신규 사용자 삽입 |
| 사용자 삭제 | `state/admin.py` → `delete_user()` | 사용자 레코드 삭제 |
| 권한 변경 | `state/admin.py` → `toggle_admin()` | 관리자 권한 토글 |
| 앱 시작 | Reflex 내부 | 테이블 자동 생성/마이그레이션 |

## 관련 파일 목록

| 파일 | 역할 |
|------|------|
| `pyproject.toml` | DB 관련 의존성 선언 (sqlmodel, pymysql, aiomysql 등) |
| `rxconfig.py` | DB 연결 URL 설정 (db_url) |
| `wellbot/models.py` | 테이블 모델 정의 |
| `wellbot/state/auth.py` | 인증 관련 DB 조회 (로그인) |
| `wellbot/state/admin.py` | 사용자 관리 CRUD |

## 실제 데이터베이스 스키마 (MySQL)

> 출처: `docs/database_schema.xlsx`

### 테이블 전체 목록

| # | 논리명 | 물리명 | 용도 |
|---|--------|--------|------|
| 1 | 부서마스터 | DEPT_M | 부서 (일일/월간 토큰 쿼터, 허용 모델) |
| 2 | 사원마스터 | EMP_M | 사용자 계정 (역할, 상태, 잠금) |
| 3 | 인증토큰내역 | CRTF_TOKN_N | 사용자별 인증 토큰 관리 |
| 4 | 챗봇요약상세 | CHTB_SMRY_D | 대화 세션 (제목, 모델, 즐겨찾기) |
| 5 | 챗봇메시지상세 | CHTB_MSG_D | 개별 메시지 (토큰 수, 응답시간, 첨부파일) |
| 6 | 첨부파일마스터 | ATCH_FILE_M | 첨부파일 메타 (S3 경로, 토큰 수) |
| 7 | 에이전트마스터 | AGENT_M | 지원 Agent 목록 (프레임워크, 경로, 설명) |
| 8 | 에이전트메모리사용내역 | AGENT_MEM_USE_N | Agent 메모리 사용 이력 |

---

### 1. 부서마스터 (DEPT_M)

부서별 일일/월간 토큰 쿼터 및 허용 모델을 관리한다.

| 논리명 | 컬럼명 | 데이터타입 | PK | FK | NOT NULL | 비고 |
|--------|--------|-----------|----|----|----------|------|
| 부서코드 | DEPT_CD | VARCHAR(8) | PK | | | |
| 부서명 | DEPT_NM | VARCHAR(50) | UK | | | |
| 일별토큰개수 | DD_TOKN_ECNT | NUMERIC(10) | | | | |
| 월별토큰개수 | MM_TOKN_ECNT | NUMERIC(10) | | | | |
| 허용모델내용 | ACES_MDL_CNTT | JSON | | | | |
| 등록일시 | RGST_DTM | datetime | | | Y | |
| 등록자아이디 | RGST_ID | VARCHAR(20) | | | Y | |
| 수정일시 | UPD_DTM | datetime | | | Y | |
| 수정자아이디 | UPPR_ID | VARCHAR(20) | | | Y | |

---

### 2. 사원마스터 (EMP_M)

사용자 계정 정보. 역할(super-admin/admin/user), 계정 상태(active/inactive/locked), 로그인 실패 관리를 포함한다.

| 논리명 | 컬럼명 | 데이터타입 | PK | FK | NOT NULL | 비고 |
|--------|--------|-----------|----|----|----------|------|
| 사원번호 | EMP_NO | VARCHAR(15) | PK | | | |
| 사용자명 | USER_NM | VARCHAR(50) | | | | |
| 이메일주소 | EML_ADDR | VARCHAR(100) | UK | | | |
| 암호화비밀번호 | ECR_PWD | VARCHAR(255) | | | | |
| 사용자역할명 | USER_ROLE_NM | VARCHAR(50) | | | Y | super-admin / admin / user |
| 소속부서코드 | PSTN_DEPT_CD | VARCHAR(8) | | FK | Y | → DEPT_M.DEPT_CD |
| 계정상태명 | ACNT_STS_NM | VARCHAR(50) | | | Y | active / inactive / locked |
| 로그인성공일시 | LGN_SCS_DTM | datetime | | | | |
| 로그인실패횟수 | LGN_FLR_TSCNT | NUMERIC(5) | | | Y | |
| 잠금해제일시 | LOCK_DSBN_DTM | datetime | | | | |
| 사용자UUID | USER_UUID | VARCHAR(36) | | | | |
| 등록일시 | RGST_DTM | datetime | | | Y | |
| 등록자아이디 | RGST_ID | VARCHAR(20) | | | Y | |
| 수정일시 | UPD_DTM | datetime | | | Y | |
| 수정자아이디 | UPPR_ID | VARCHAR(20) | | | Y | |

---

### 3. 인증토큰내역 (CRTF_TOKN_N)

사용자별 인증 토큰을 관리한다. JWT 등 토큰 기반 인증에 사용.

| 논리명 | 컬럼명 | 데이터타입 | PK | FK | NOT NULL | 비고 |
|--------|--------|-----------|----|----|----------|------|
| 사원번호 | EMP_NO | VARCHAR(15) | PK | | | |
| 인증토큰아이디 | CRTF_TOKN_ID | VARCHAR(50) | PK | | | 시퀀스 |
| 인증암호화토큰값 | CRTF_TOKN_ECR_CNTT | VARCHAR(300) | | | Y | |
| 폐기여부 | DISS_YN | VARCHAR(1) | | | | |
| 만료일시 | TRTN_DTM | datetime | | | | |
| 폐기일시 | DISS_DTM | datetime | | | | |
| 등록일시 | RGST_DTM | datetime | | | Y | |
| 등록자아이디 | RGST_ID | VARCHAR(20) | | | Y | |
| 수정일시 | UPD_DTM | datetime | | | Y | |
| 수정자아이디 | UPPR_ID | VARCHAR(20) | | | Y | |

---

### 4. 챗봇요약상세 (CHTB_SMRY_D)

대화 세션 단위 정보. 사이드바의 대화 이력 목록에 해당한다.

| 논리명 | 컬럼명 | 데이터타입 | PK | FK | NOT NULL | 비고 |
|--------|--------|-----------|----|----|----------|------|
| 챗봇대화요약ID | CHTB_TLK_SMRY_ID | VARCHAR(50) | PK | | | 대화 세션 아이디 |
| 사원번호 | EMP_NO | VARCHAR(20) | | | Y | |
| 챗봇대화요약제목 | CHTB_TLK_SMRY_TTL | VARCHAR(255) | | | | |
| 챗봇모델명 | CHTB_MDL_NM | VARCHAR(100) | | | | |
| 즐겨찾기여부 | BKMR_YN | VARCHAR(1) | | | | |
| 등록일시 | RGST_DTM | datetime | | | Y | |
| 등록자아이디 | RGST_ID | VARCHAR(20) | | | Y | |
| 수정일시 | UPD_DTM | datetime | | | Y | |
| 수정자아이디 | UPPR_ID | VARCHAR(20) | | | Y | |

---

### 5. 챗봇메시지상세 (CHTB_MSG_D)

개별 메시지 레코드. 토큰 사용량, 응답시간, 첨부파일 참조를 포함한다.

| 논리명 | 컬럼명 | 데이터타입 | PK | FK | NOT NULL | 비고 |
|--------|--------|-----------|----|----|----------|------|
| 챗봇대화요약ID | CHTB_TLK_SMRY_ID | VARCHAR(50) | PK | | | 대화 세션 아이디 |
| 챗봇대화아이디 | CHTB_TLK_ID | VARCHAR(50) | | | | 메시지 아이디 |
| 에이전트아이디 | AGNT_ID | VARCHAR(50) | | | | |
| 메시지역할명 | MSG_ROLE_NM | VARCHAR(50) | | | | user / assistant / system |
| 챗봇메시지내용 | CHTB_MSG_CNTT | MEDIUMTEXT | | | | |
| 챗봇모델명 | CHTB_MDL_NM | VARCHAR(100) | | | | |
| 챗봇제공모델명 | CHTB_OFFR_MDL_NM | VARCHAR(50) | | | | Anthropic / AWS / Cohere 등 |
| 챗봇입력토큰개수 | CHTB_INPUT_TOKN_ECNT | NUMERIC(10) | | | | |
| 챗봇출력토큰개수 | CHTB_OUTPUT_TOKN_ECNT | NUMERIC(10) | | | | |
| 챗봇총토큰개수 | CHTB_TOT_TOKN_ECNT | NUMERIC(10) | | | | |
| 응답시간 | RPLY_TIME | NUMERIC(5,2) | | | | |
| 첨부파일번호 | ATCH_FILE_NO | BIGINT(15) | | | | 시퀀스 |
| 등록일시 | RGST_DTM | datetime | | | Y | |
| 등록자아이디 | RGST_ID | VARCHAR(20) | | | Y | |
| 수정일시 | UPD_DTM | datetime | | | Y | |
| 수정자아이디 | UPPR_ID | VARCHAR(20) | | | Y | |

---

### 6. 첨부파일마스터 (ATCH_FILE_M)

첨부파일 메타데이터. S3 경로 및 토큰 수를 관리한다.

| 논리명 | 컬럼명 | 데이터타입 | PK | FK | NOT NULL | 비고 |
|--------|--------|-----------|----|----|----------|------|
| 챗봇대화아이디 | CHTB_TLK_ID | VARCHAR(50) | PK | | | |
| 첨부파일번호 | ATCH_FILE_NO | BIGINT(15) | PK | | | 시퀀스 |
| 첨부파일명 | ATCH_FILE_NM | VARCHAR(255) | | | | |
| 첨부파일URL주소 | ATCH_FILE_URL_ADDR | VARCHAR(500) | | | | S3 path |
| 첨부파일토큰개수 | ATCH_TOKN_ECNT | NUMERIC(10) | | | | |
| 등록일시 | RGST_DTM | datetime | | | Y | |
| 등록자아이디 | RGST_ID | VARCHAR(20) | | | Y | |
| 수정일시 | UPD_DTM | datetime | | | Y | |
| 수정자아이디 | UPPR_ID | VARCHAR(20) | | | Y | |

---

### 7. 에이전트마스터 (AGENT_M)

지원 Agent 목록. 관리자가 설정하는 프레임워크, 경로(ARN/스크립트), 설명 등을 관리한다.

| 논리명 | 컬럼명 | 데이터타입 | PK | FK | NOT NULL | 비고 |
|--------|--------|-----------|----|----|----------|------|
| 에이전트아이디 | AGENT_ID | VARCHAR(50) | PK | | | |
| 에이전트순번 | AGENT_SEQ | NUMERIC(10) | PK | | | |
| 에이전트명 | AGENT_NM | VARCHAR(100) | | | Y | |
| 에이전트프레임워크명 | AGENT_FRWK_NM | VARCHAR(100) | | | Y | 관리자에서 설정하는 값 |
| 에이전트경로주소 | AGENT_PATH_ADDR | VARCHAR(300) | | | Y | ARN, 스크립트 경로 등 |
| 에이전트상세설명 | AGENT_DSCR_CNTT | MEDIUMTEXT | | | | 에이전트 설명 |
| 사용여부 | USE_YN | VARCHAR(1) | | | Y | 사용 여부 |
| 등록일시 | RGST_DTM | datetime | | | Y | |
| 등록자아이디 | RGST_ID | VARCHAR(20) | | | Y | |
| 수정일시 | UPD_DTM | datetime | | | Y | |
| 수정자아이디 | UPPR_ID | VARCHAR(20) | | | Y | |

---

### 8. 에이전트메모리사용내역 (AGENT_MEM_USE_N)

Agent별 메모리 사용 이력. 프레임워크 유형(AgentCore, LangGraph 등)과 동기화 상태를 추적한다.

| 논리명 | 컬럼명 | 데이터타입 | PK | FK | NOT NULL | 비고 |
|--------|--------|-----------|----|----|----------|------|
| 에이전트아이디 | AGENT_ID | VARCHAR(100) | PK | | | |
| 에이전트순번 | AGENT_SEQ | NUMERIC(10) | PK | | | |
| 사원번호 | EMP_NO | VARCHAR(100) | PK | | Y | |
| 에이전트메모리경로주소 | AGENT_MEM_PATH_ADDR | VARCHAR(300) | | | | |
| 에이전트유형설명내용 | AGENT_TYPE_DSCR_CNTT | MEDIUMTEXT | | | Y | AgentCore, LangGraph 등 |
| 사용여부 | USE_YN | VARCHAR(1) | | | Y | 사용 여부 |
| 최종동기화일시 | LAST_SYNC_DTM | datetime | | | | |
| 등록일시 | RGST_DTM | datetime | | | Y | |
| 등록자아이디 | RGST_ID | VARCHAR(20) | | | Y | |
| 수정일시 | UPD_DTM | datetime | | | Y | |
| 수정자아이디 | UPPR_ID | VARCHAR(20) | | | Y | |

---

### 테이블 관계 (ERD 요약)

```
DEPT_M (부서)
  │
  └─── 1:N ──→ EMP_M (사원)  ← PSTN_DEPT_CD → DEPT_CD
                 │
                 ├─── 1:N ──→ CRTF_TOKN_N (인증토큰)  ← EMP_NO
                 │
                 └─── 1:N ──→ CHTB_SMRY_D (대화세션)  ← EMP_NO
                                │
                                └─── 1:N ──→ CHTB_MSG_D (메시지)  ← CHTB_TLK_SMRY_ID
                                              │
                                              └─── 1:N ──→ ATCH_FILE_M (첨부파일)  ← CHTB_TLK_ID

AGENT_M (에이전트)
  │
  └─── 1:N ──→ AGENT_MEM_USE_N (메모리사용)  ← AGENT_ID, AGENT_SEQ
                 │
                 └─── N:1 ──→ EMP_M (사원)  ← EMP_NO
```

### 공통 컬럼 패턴

모든 테이블에 아래 4개 감사(audit) 컬럼이 공통으로 존재한다:

| 컬럼명 | 데이터타입 | 용도 |
|--------|-----------|------|
| RGST_DTM | datetime | 등록일시 |
| RGST_ID | VARCHAR(20) | 등록자 아이디 |
| UPD_DTM | datetime | 수정일시 |
| UPPR_ID | VARCHAR(20) | 수정자 아이디 |

---

### 현재 코드 모델과의 차이점

현재 `wellbot/models.py`의 `User` 모델은 실제 DB 스키마와 큰 차이가 있다:

| 항목 | 현재 코드 (User) | 실제 DB (EMP_M) |
|------|-----------------|-----------------|
| 테이블명 | wellbot_user | EMP_M |
| PK | id (자동 생성) | EMP_NO (사원번호) |
| 사용자 식별 | username | EMP_NO + USER_NM + EML_ADDR |
| 비밀번호 | password_hash | ECR_PWD |
| 권한 | is_admin (bool) | USER_ROLE_NM (super-admin/admin/user) |
| 부서 | 없음 | PSTN_DEPT_CD (FK → DEPT_M) |
| 계정 상태 | 없음 | ACNT_STS_NM (active/inactive/locked) |
| 로그인 실패 관리 | 없음 | LGN_FLR_TSCNT, LOCK_DSBN_DTM |
| 감사 컬럼 | 없음 | RGST_DTM, RGST_ID, UPD_DTM, UPPR_ID |

또한 현재 코드에 존재하지 않는 테이블이 7개 (DEPT_M, CRTF_TOKN_N, CHTB_SMRY_D, CHTB_MSG_D, ATCH_FILE_M, AGENT_M, AGENT_MEM_USE_N) 있으며, `models.py` 전면 재작성이 필요하다.

## 참고사항

- 채팅 이력(`ChatState.chat_history`)은 현재 메모리(State)에만 저장되며, DB에 영속화되지 않음
- 향후 대화 이력 저장이 필요하면 별도 모델(예: `ChatMessage`) 정의 및 DB 저장 로직 추가 필요
- `state/auth.py`의 `check_auth()`에 `TODO: after set Database` 주석이 있어, DB 설정 완료 후 인증 체크 활성화 예정
