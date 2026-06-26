# KB 기능 이식 계획서 (wellbot-merge → wellbot-main)

> 작성일: 2026-06-01
> 출발지: `wellbot-merge` (KB 기능 보유, 구(舊) 평탄 구조)
> 목적지: `wellbot-main` (KB 기능 없음, 리팩토링 1~4단계 완료된 도메인 그룹 구조)

본 문서는 wellbot-merge 의 Knowledge Base(개인/팀/공용) 기능을, 구조가 크게 달라진 wellbot-main 에 이식하기 위한 실행 계획이다. 각 단계는 독립 커밋 가능하도록 설계했고, 위험도 순으로 정렬했다(쉬운 것 먼저).

---

## 0. 핵심 전제 — 두 프로젝트의 구조 차이

| 영역 | wellbot-merge (출발) | wellbot-main (목적) |
| --- | --- | --- |
| services 구성 | 평탄 (`services/*.py`) | 도메인 그룹 (`services/{auth,chat,ai/bedrock,files,core,admin}/`) |
| 설정 모듈 | `services/config.py` | `services/core/settings.py` |
| DB 모듈 | `services/database.py` | `services/core/database.py` |
| Bedrock | `services/bedrock_client.py` | `services/ai/bedrock/{client,converse,...}.py` |
| 임베딩 | `services/embedding_service.py` | `services/ai/embedding_service.py` |
| 스토리지 | `services/storage_service.py` | `services/files/storage_service.py` |
| 첨부 | `services/attachment_service.py` | `services/files/attachment_service.py` |
| 인증 | `services/auth_service.py` | `services/auth/auth_service.py` |
| tool 실행 | `services/tool_executor.py` | `services/chat/tool_executor.py` |
| chat_state | 단일 1849줄 | 859줄 + `state/chat_helpers/` + `chat_models.py` |
| 경로 상수 | 인라인 `Path(__file__)...` | `wellbot/paths.py` |
| env 로딩 | `config.py` 모듈 레벨 `load_dotenv()` | `wellbot/env.py::init_env()` 명시 호출 |
| 모델 별칭 | `EmpM` 등 약어만 | `Employee`/`EmpM` alias 병행 (약어 호환 유지) |

**중요 1 — 모델 import 무수정**: wellbot-main 은 `AgntMmryUseN`, `EmpM` alias 를 유지하므로 KB 파일의 `from wellbot.models import AgntMmryUseN, EmpM` 는 그대로 동작.

**중요 2 — env 로딩 순서**: wellbot-main 은 모듈 레벨 `load_dotenv()` 를 제거하고 `init_env()` 명시 호출로 바꿨다. KB 모듈 다수가 모듈 레벨에서 `os.getenv(...)` 로 설정을 읽으므로(예: `kb_utils.py` 의 `S3_BUCKET = _kb_cfg["s3_bucket"]`), **반드시 `init_env()` 이후에 import** 되어야 한다. 엔트리포인트 경유 import 는 안전하지만, `scripts/` 의 KB 스크립트는 자체적으로 `init_env()` 를 먼저 호출해야 한다.

---

## 1. Import 경로 일괄 변환표 (전 단계 공통 기준)

KB 파일을 옮길 때 내부의 모든 import 를 아래 표대로 치환한다.

| 구 경로 (merge) | 신 경로 (main) |
| --- | --- |
| `wellbot.services.config` (`get_kb_config`) | `wellbot.services.knowledgebase.config` ※ 1.1 참조 |
| `wellbot.services.database` | `wellbot.services.core.database` |
| `wellbot.services.embedding_service` | `wellbot.services.ai.embedding_service` |
| `wellbot.services.storage_service` | `wellbot.services.files.storage_service` |
| `wellbot.services.attachment_service` | `wellbot.services.files.attachment_service` |
| `wellbot.services.auth_service` | `wellbot.services.auth.auth_service` |
| `wellbot.services.bedrock_client` | `wellbot.services.ai.bedrock` |
| `wellbot.services.tool_executor` | `wellbot.services.chat.tool_executor` |
| `wellbot.services.kb_retriever` | `wellbot.services.knowledgebase.kb_retriever` |
| `wellbot.services.kb_utils` | `wellbot.services.knowledgebase.kb_utils` |
| `wellbot.services.personal_kb_manager` | `wellbot.services.knowledgebase.personal_kb_manager` |
| `wellbot.services.team_kb_manager` | `wellbot.services.knowledgebase.team_kb_manager` |
| `wellbot.models` (`AgntMmryUseN`, `EmpM`) | 무변경 (alias 유지) |
| `wellbot.constants` (`KST`, `KB_*`) | 무변경 (KB 상수는 2단계에서 추가) |

### 1.1 `get_kb_config` 배치 결정
- merge 에서는 공용 `services/config.py` 안에 있으나, KB 전용 로직이다.
- **권장**: KB 도메인 패키지 안 `services/knowledgebase/config.py` 로 이동 (main 의 도메인 그룹 철학에 부합, `core/settings.py` 를 KB 무관하게 유지).
- knowBase.yaml 경로는 `wellbot/paths.py` 에 `KNOWBASE_YAML` 상수 추가 후 참조.

---

## 2. 작업 단계

### 단계 1 — KB 전용 파일 이동 + import 경로 치환 (위험 低)

**1-A. `services/knowledgebase/` 패키지 신설**
```
wellbot/services/knowledgebase/
  __init__.py          # 공개 API 재노출
  config.py            # get_kb_config (구 config.py 의 KB 부분 + _KB_INFRA_ENV_KEYS)
  kb_retriever.py      # ← merge/services/kb_retriever.py
  kb_utils.py          # ← merge/services/kb_utils.py
  personal_kb_manager.py
  team_kb_manager.py
```
- 4개 파일 복사 후 1번 표대로 import 치환.
- 패키지 내부 상호 참조도 절대경로로: `from wellbot.services.knowledgebase.kb_utils import ...`
- `__init__.py` 에서 호출부가 쓰는 심볼 재노출: `retrieve`, `get_user_kb`, `get_user_team_kb`, `get_dept_cd`, `get_or_create_personal_kb`, `upload_and_ingest`(개인/팀), `start_ingestion`, `is_ingestion_in_progress`, `poll_ingestion_status`, `_insert_user_kb`, `ensure_team_kb_membership` 등.

**1-B. `wellbot/paths.py` 에 KB 경로 추가**
```python
KNOWBASE_YAML: Path = CONFIG_DIR / "knowBase.yaml"
```

**1-C. KB API 파일 이동**
- `api/kb_upload.py`, `api/kb_download.py` → wellbot-main `api/` 로 복사 + import 치환.
- `kb_download.py` 의 `auth_service` → `wellbot.services.auth.auth_service`, `get_dept_cd` → `knowledgebase.team_kb_manager`.
- 로깅: main 은 `log_context` 기반 → 필요 시 main 의 `download.py` 패턴 참고하여 정합화(필수 아님).

**1-D. KB 컴포넌트/설정/스크립트 이동**
- `components/chat/file_icon.py` → 그대로 복사 (의존성 확인).
- `config/knowBase.yaml` → 그대로 복사.
- `scripts/{cleanup_personal_kb,shared_kb_manager,transform_lambda}.py` → 복사 + import 치환 + **각 스크립트 진입부에 `from wellbot.env import init_env; init_env()` 추가** (모듈 레벨 os.getenv 보장).

**검증**: `python -c "import wellbot.services.knowledgebase"` 류로 import 그래프 확인. (DB/AWS 자격증명 없이도 import 성공해야 함 — 단계 1 후 점검.)

---

### 단계 2 — 저위험 공유 파일 통합 (위험 低)

**2-A. `constants.py`** — KB 상수 3종 추가
```python
# ── KB (Knowledge Base) ──
KB_SEARCH_TOP_K: int = 5
KB_MIN_SCORE: float = 0.4
KB_NOT_FOUND_PATTERNS: tuple[str, ...] = (...)  # merge constants.py:80-86 그대로
```

**2-B. `get_kb_config`** — `services/knowledgebase/config.py` 로 (1.1). `paths.KNOWBASE_YAML` 사용하도록 경로만 조정.

**2-C. `api/app.py`** — 라우터 2개 등록
```python
from wellbot.api.kb_upload import router as kb_upload_router
from wellbot.api.kb_download import router as kb_download_router
...
api_app.include_router(kb_upload_router)
api_app.include_router(kb_download_router)
```

**2-D. `state/chat_models.py`** — `Message` 에 `source_docs` 필드 추가 (merge chat_state.py:104). KB 출처 표시용. 타입은 merge 정의 확인 후 이식.

**2-E. `components/chat/message_bubble.py`** — 출처 칩 (merge message_bubble.py:19-74)
- `_source_chip`, `_source_docs_section` 함수 추가.
- `ai_message()` 에 `_source_docs_section(message)` 삽입 (현재 main message_bubble.py:82 `_ai_message_actions` 근처).

**2-F. `pages/index.py`** — `KB_UPLOAD_SCRIPT` 주입
- `from wellbot.components.chat.input_bar import KB_UPLOAD_SCRIPT` (4단계 후 존재).
- 페이지에 `rx.script(KB_UPLOAD_SCRIPT)` 추가 (AUTO_SCROLL_SCRIPT 와 동일 패턴).

**2-G. `.env.example`** — KB 인프라 키 추가 (merge .env.example KB 섹션). `S3_BUCKET_NAME` 통일 여부는 merge 측 최신 결정 반영.

---

### 단계 3 — `services/chat/tool_executor.py` KB 검색 도구 (위험 低, 통째 이동)

**확인 완료**: merge `tool_executor.py` 는 main 의 **strict superset**. `search_attachment` 관련 4개 심볼(`SEARCH_ATTACHMENT_TOOL`, `_format_search_result`, `_run_search_attachment`, `parse_tool_input`)은 **완전 동일**(main 이 tool 로직은 리팩토링하지 않음). merge 추가분 = `KB_SEARCH_TOOL` + `_run_kb_search` + `execute_tool` 의 kb_search 분기 + emp_no 파라미터.

**방법**: merge `tool_executor.py` 를 main `services/chat/tool_executor.py` 로 **통째 복사** 후 import 2줄만 치환.
```python
from wellbot.services import embedding_service             # → from wellbot.services.ai import embedding_service
from wellbot.services.kb_retriever import retrieve as kb_retrieve  # → from wellbot.services.knowledgebase import ...
```
- `from wellbot.constants import KB_SEARCH_TOP_K, SEARCH_TOP_K` 는 2-A 에서 `KB_SEARCH_TOP_K` 추가 후 OK.
- **`build_tool_config()` 무변경**: merge 도 무조건 `[SEARCH_ATTACHMENT_TOOL, KB_SEARCH_TOOL]` 반환. 조건 분기(`has_attachments or use_kb`)는 chat_state(5-F)에 있음.
- **emp_no 경로 무설계**: merge `execute_tool(name, input, smry_id, emp_no="")` 이미 emp_no 수용. chat_state 의 `_tool_exec` 클로저가 emp_no + kb_modes 주입(5-F 에서 이식).

---

### 단계 4 — `components/chat/input_bar.py` KB UI (위험 中, 분량 大)

merge input_bar.py 는 KB UI 로 ~860줄 증가(416→1284). 대부분 **독립 컴포넌트 함수**라 이식은 가능하나 분량이 크다.

이식 대상 (merge 기준 라인):
| 블록 | merge 라인 | 설명 |
| --- | --- | --- |
| `KB_UPLOAD_SCRIPT` | 25-86 | 파일 피커 JS 상수 (2-F 에서 참조) |
| `_kb_flyout` | 206-320 | 검색 범위 hover card |
| `_scope_checkbox` | 495-507 | 범위 체크박스 |
| `_pending_file_row` | 510-534 | 업로드 대기 파일 행 |
| `_kb_docs_tab_btn` | 537-560 | 개인/팀/공용 탭 버튼 |
| `_kb_doc_row` | 563-624 | 문서 행 |
| `_kb_shared_file_row` | 627-671 | 공용 KB 파일 행 |
| `_kb_folder_row` | 674-736 | 공용 KB 폴더 행 |
| `_kb_docs_panel` | 739-936 | 문서 목록 패널 |
| `_kb_upload_panel` | 939-1113 | 업로드 패널 |
| `_ingestion_banner` | 1116-1132 | 상태 배너 |
| `input_bar()` 본문 통합 | 1182-1200 | 패널/모드 표시 삽입 |

- 의존: `file_icon.py`(1-D 이식), `ChatState` 의 KB var/handler(5단계).
- main 의 `input_bar()` 레이아웃에 KB 패널·flyout·배너를 끼워넣는 부분이 핵심 — main 의 현재 input_bar 구조와 대조 후 삽입 지점 확정.

---

### 단계 5 — `state/chat_state.py` KB 재이식 (위험 高, 핵심 난관)

merge 의 chat_state(1849줄)는 KB 가 send/streaming 전반에 침투. main(859줄)은 헬퍼 추출 구조라 **그대로 복붙 불가** — 새 구조에 맞춰 재배치.

**5-A. 데이터 모델** (chat_models.py)
- `PendingFile`, `KbSharedFile`, `KbSharedFolder` 클래스 추가 (merge:72-92).

**5-B. State 필드** (ChatState 클래스)
- KB 상태 필드 ~22개 추가 (merge:187-208): `kb_modes`, `upload_target`, `dept_cd`, `personal_kb_exists`, `team_kb_exists`, `kb_flyout_open`, `ingestion_status`, `pending_files`, `active_panel`, `kb_doc_list`, `selected_kb_docs`, `kb_folder_list`, `expanded_kb_folders` 등.

**5-C. Computed vars**
- `use_kb`, `kb_mode_display`, `kb_docs_empty`, `kb_delete_button_label` (merge:474-489, 733-742).

**5-D. Event handlers** (대부분 독립 — main 끝부분에 추가)
- 업로드: `open_file_picker`, `add_pending_files_from_js`, `remove_pending_file`, `clear_pending_files`, `confirm_upload_via_api`, `on_upload_complete` (merge:1103-1308).
- 문서목록/삭제: `set_kb_doc_list_tab`, `toggle_kb_doc_selection`, `toggle_kb_folder`, `confirm_kb_delete`, `load_kb_docs` (merge:699-966).
- 모드/플라이아웃: `set_upload_target`, `toggle_kb_scope_inline`, `toggle_kb_mode`, `on_plus_menu_open_change`, `on_kb_flyout_open_change`, `close_kb_flyout` (merge:968-1016).
- 출처 다운로드: `download_kb_source` (merge:1018-1076) — main 의 `download_attachment`/`build_download_script` 패턴과 정합화 권장.

**5-E. `on_load` 통합** (merge:510-530)
- main `on_load`(357-417) 의 emp_no 취득 직후에 개인/팀 KB 존재 확인 + 팀 membership 자동 등록 삽입.

**5-F. `send_message` 훅** — 가장 정밀한 작업. main send_message(684-993) 의 정확한 지점에 삽입:
| 훅 | main 삽입 지점 | 내용 |
| --- | --- | --- |
| use_kb/kb_modes 캡처 | 락 안, 로컬 변수 영역 (~773-779) | `use_kb = self.use_kb`, `kb_modes = list(self.kb_modes)` |
| 시스템 프롬프트 augment | line 848 직후 | `system_prompt = augment_system_with_kb(system_prompt, ...)` (헬퍼화) |
| tool_config 에 KB 추가 | line 856-879 분기 | `if has_attachments or use_kb:` 로 조건 확장. `build_tool_config()` 무변경 |
| tool_executor emp_no/kb_modes 전달 | `_tool_exec` 클로저(868) | `if name=="kb_search": tool_input={**tool_input,"kb_scope":kb_modes}` + `execute_tool(name, input, conv_id, emp_no)` (merge:1940-1944) |
| 출처 누적 | `tool_result` 이벤트(906-908, 현재 pass) | kb_search 결과의 source_docs 수집 |
| 출처 필터링 | ai_msg 생성 직전(930) | 인용 마커 추출 → source_docs 필터 → `Message(..., source_docs=...)` |

**5-G. 헬퍼 추출** (main 철학 준수)
- `_augment_system_with_kb` (merge:1678-1740) → `state/chat_helpers/system_prompt.py` 에 `augment_system_with_kb()` 로 추가 (기존 `augment_system_with_attachments` 옆).
- **KB 다운로드 JS → `chat_helpers/download_script.py` 에 `build_kb_download_script(s3_uri, filename)` 추가** (확인 완료: merge `download_kb_source` 의 JS 가 main `build_download_script` 와 구조 동일. 차이는 엔드포인트 `/api/download_kb` + JSON body 뿐). State 핸들러는 thin wrapper 로:
  ```python
  def download_kb_source(self, s3_uri, filename):
      return rx.call_script(build_kb_download_script(s3_uri, filename))
  ```
- KB 출처 필터링 로직(인용 마커 추출 → rank 필터) → `chat_helpers/` 에 순수 함수로 추출 검토.
- KB 업로드 JS 빌더(`KB_UPLOAD_SCRIPT`)는 merge 에서 input_bar.py 에 상주(4단계). main 패턴상 `chat_helpers/` 또는 input_bar 유지 — 4단계에서 결정.

---

## 3. 검증 전략

| 단계 | 검증 |
| --- | --- |
| 1 | `python -c "import wellbot.services.knowledgebase"` (자격증명 없이 import 성공) |
| 2 | `python -c "import wellbot.wellbot"` import 그래프 OK + `get_kb_config()` 로드 |
| 3 | tool_executor 단위 호출 — `build_tool_config(include_kb=True)` 구조 확인 |
| 4 | `reflex run` 기동 후 KB 패널/플라이아웃 렌더 확인 |
| 5 | 시나리오 수동 테스트: 개인 KB 업로드→ingest→검색→인용 출처 표시→다운로드 / 팀 KB / 공용 KB / KB 미사용 회귀 |

전 단계 공통: 각 단계 후 `python -m py_compile` + `reflex run` 기동 확인.

---

## 4. 위험 요소

1. **chat_state send_message 훅 (5-F)** — 가장 깨지기 쉬움. main 의 background 이벤트 + `async with self` 락 패턴 안에서 KB 상태 접근 위치를 정확히 지켜야 함. (최대 난관)
2. ~~tool_executor emp_no 경로~~ — **해소**. merge `execute_tool(..., emp_no="")` 이미 수용, `_tool_exec` 클로저가 주입(merge:1940-1944).
3. **env 로딩 순서 (0-중요2)** — KB 모듈 모듈레벨 os.getenv. init_env 선행 보장 필수. 스크립트는 자체 호출.
4. ~~build_tool_config 시그니처 변경~~ — **해소**. merge 도 무조건 반환, 조건은 chat_state. 무변경.
5. **input_bar 레이아웃 통합 (4)** — main 과 merge 의 input_bar() 본문 구조 차이. 삽입 지점 대조 필수.
6. **file_icon.py 의존성 (1-D)** — styles/icons 등 main 측 의존 심볼 존재 확인.
7. **`_streaming_kb_sources` 임시 State 필드 (5-F)** — merge 가 스트리밍 중 출처 누적에 사용(merge:1991). 5-B 필드 목록에 포함 필요.

---

## 5. 결정 완료 사항 (2026-06-01)

1. **`get_kb_config` 위치** → `knowledgebase/config.py` **확정**. (도메인 응집·제거 용이성·core 핫패스 격리)
2. **KB 출처 다운로드** → `chat_helpers/download_script.py` 에 `build_kb_download_script` 추출 **확정**. (main 패턴과 동일, 5-G)
3. **tool_executor KB 이식** → merge 파일 **통째 이동** + import 2줄 치환 **확정**. emp_no/build_tool_config 무변경.
4. **진행 순서** → 쉬운 것부터 순서대로(1→2→3→4→5) **확정**.

---

## 진행 체크리스트

- [ ] 1-A `services/knowledgebase/` 패키지 + 4파일 이동 + import 치환
- [ ] 1-B `paths.py` KNOWBASE_YAML
- [ ] 1-C KB API 2파일 이동
- [ ] 1-D file_icon / knowBase.yaml / scripts 이동
- [ ] 2-A constants KB 상수
- [ ] 2-B get_kb_config 이동
- [ ] 2-C app.py 라우터
- [ ] 2-D chat_models Message.source_docs
- [ ] 2-E message_bubble 출처 칩
- [ ] 2-F pages/index KB_UPLOAD_SCRIPT
- [ ] 2-G .env.example
- [ ] 3 tool_executor KB_SEARCH_TOOL + _run_kb_search
- [ ] 4 input_bar KB UI 컴포넌트
- [ ] 5-A chat_models KB 데이터 모델
- [ ] 5-B~5-C State 필드 + computed
- [ ] 5-D event handlers
- [ ] 5-E on_load 통합
- [ ] 5-F send_message 훅
- [ ] 5-G 헬퍼 추출
- [ ] 최종 시나리오 수동 검증
