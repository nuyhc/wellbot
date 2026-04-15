# PRD: 대화 세션 내 파일 첨부 및 RAG 활용 기능

**문서 버전**: 1.0
**작성일**: 2026-04-15
**상태**: ✅ FINAL
**대상 프로젝트**: WellBot (Reflex + AWS Bedrock 챗봇)

---

## 1. 개요

### 1.1 목적

WellBot 챗봇에 파일 첨부 기능을 추가하여, 사용자가 업로드한 문서를 대화 세션 내에서 지속적으로 활용할 수 있게 한다. S3 에 원본 + 파생물(청크/인덱스)을 저장하고, LLM 이 Tool Use 로 자율 검색하여 정확한 답변을 제공하는 구조.

### 1.2 핵심 흐름

```
[사용자]
  ├─(1) 파일 업로드
  │     └─> FastAPI Route → S3 Multipart Streaming
  │              ├─> original.{ext}    (원본)
  │              ├─> 파싱 → 청킹 → Bedrock Titan 임베딩
  │              ├─> chunks.jsonl      (청크 텍스트)
  │              └─> index.faiss       (FAISS 인덱스)
  │     └─> atch_file_m INSERT (s3 prefix 저장)
  │     └─> chtb_msg_atch_file_d INSERT (대화 매핑)
  │
  ├─(2) 메시지 전송
  │     └─> system prompt 에 파일 메타 목록만 주입 (~100 토큰)
  │     └─> Bedrock Converse + toolConfig(search_attachment)
  │     └─> LLM 이 필요 시 tool 호출 → FAISS 검색 → 청크 반환
  │     └─> 최종 응답 스트리밍
  │
  └─(3) 이미지 파일
        └─> Bedrock Converse `image` block 직접 전달
```

### 1.3 확정된 기술 결정

| 항목 | 결정 |
|------|------|
| 업로드 | FastAPI custom route (`@rx.api`) + S3 multipart streaming |
| 스토리지 | AWS S3 (서버 프록시, presigned URL 미사용) |
| 파싱 | 로컬 + Upstage 하이브리드 (`FILE_PARSER_MODE` 설정 전환) |
| 이미지 | Bedrock Converse `image` block (모든 멀티모달 모델) |
| 컨텍스트 주입 | **파일 메타만 주입** + Tool Use 검색 (요약 X) |
| 벡터 저장 | **FAISS (메모리) + S3 파생물 (chunks.jsonl + index.faiss)** |
| 임베딩 | Bedrock Titan Embeddings V2 |
| 세션 유지 | 대화 단위 |
| Reflex 버전 | 0.8.28 유지 |
| **DB 변경** | **0건** (기존 `atch_file_m`, `chtb_msg_atch_file_d` 활용) |
| S3 버킷 | `wellbot-014498622157-ap-northeast-2-an` (생성 완료) |
| AWS 인증 | 환경변수 기반 (Bedrock 과 동일 자격증명) |
| S3 권한 | FullAccess (부여 완료) |

---

## 2. 지원 파일 타입 & 제한

### 2.1 파일 타입 매트릭스

| 확장자 | MIME | 로컬 파서 | Upstage | 자동 분할 | 분할 불가 시 정책 |
|--------|------|----------|---------|----------|-----------------|
| `.pdf` | application/pdf | `pdfplumber` | ✅ | ✅ (페이지/용량) | — |
| `.docx` | ...wordprocessingml | `python-docx` | ✅ | ❌ | 에러 + 사용자 분할 안내 |
| `.xlsx` | ...spreadsheetml | `openpyxl` | ✅ | ❌ | 에러 + 사용자 분할 안내 |
| `.pptx` | ...presentationml | `python-pptx` | ✅ | ❌ | 에러 + 사용자 분할 안내 |
| `.hwp`/`.hwpx` | application/x-hwp* | ❌ | ✅ | ❌ | 에러 + 사용자 분할 안내 |
| `.txt` | text/plain | 내장 | passthrough | ❌ | 에러 (용량 문제 드묾) |
| `.md` | text/markdown | 내장 | passthrough | ❌ | 에러 (용량 문제 드묾) |
| `.png`/`.jpg`/`.jpeg`/`.webp` | image/* | — | ✅ (OCR) | ❌ | Bedrock Converse `image` block 직접 전달 |

**자동 분할 가능 확장자**: `{.pdf}` (페이지 단위 의미 손상 없이 분할 가능)
**그 외 확장자**: 용량/페이지 초과 시 사용자에게 "파일을 직접 분할 후 재업로드" 안내

**HWP 제약**: `FILE_PARSER_MODE in ("upstage", "hybrid")` 일 때만 업로드 허용.

### 2.2 설정값 (`wellbot/constants.py`)

```python
# ── 파일 첨부 ──
FILE_MAX_SIZE_MB: int = 50                # 파일 단일 최대 크기
FILE_MAX_PER_MESSAGE: int = 5             # 메시지당 첨부 개수
FILE_MAX_PER_CONVERSATION: int = 20       # 대화당 누적 첨부 개수
FILE_MAX_TOTAL_SIZE_MB: int = 200         # 대화당 누적 최대 용량

# ── 파서 ──
FILE_PARSER_MODE: str = "local"           # "local" | "upstage" | "hybrid"
FILE_PARSER_FALLBACK: bool = True         # local 실패 시 upstage 폴백 (hybrid 모드)

# ── Upstage DP 제약 (공식 제한) ──
UPSTAGE_MAX_PAGES: int = 100
UPSTAGE_MAX_SIZE_MB: int = 50

# ── 자동 분할 (PDF 전용) ──
AUTO_SPLIT_PDF_PAGES: int = 100           # 페이지 초과 시 분할
AUTO_SPLIT_PDF_SIZE_MB: int = 50          # 용량 초과 시 분할

# ── 분할 안전 마진 (실제 분할은 임계값보다 작게) ──
SPLIT_SAFETY_PAGES: int = 90
SPLIT_SAFETY_SIZE_MB: int = 45

# ── 청킹 & 임베딩 ──
CHUNK_SIZE_TOKENS: int = 1000
CHUNK_OVERLAP_TOKENS: int = 200
EMBEDDING_MODEL_ID: str = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSION: int = 1024

# ── 검색 ──
SEARCH_TOP_K: int = 5
TOOL_USE_MAX_ITERATIONS: int = 3          # tool 호출 무한루프 방지

# ── 이미지 ──
IMAGE_MAX_SIZE_MB: int = 5                # Bedrock Converse 제한
IMAGE_MAX_DIMENSION: int = 8000           # px

# ── FAISS 캐시 ──
FAISS_CACHE_MAX_CONVERSATIONS: int = 10   # 메모리 LRU
```

### 2.3 PDF 분할 알고리즘

```python
def split_pdf_for_upstage(pdf_path: Path) -> list[Path]:
    """Upstage 제약(페이지/용량)에 맞게 PDF 를 분할.

    - 페이지 기준: SPLIT_SAFETY_PAGES 단위 1차 분할
    - 용량 기준: 각 파트 SPLIT_SAFETY_SIZE_MB 초과 시 2차 분할 (재귀)
    - 분할 후 각 파트 파싱 결과를 페이지 순으로 concat → 통합 텍스트
    """
```

---

## 3. DB 스키마

### **변경 없음.** 기존 테이블 그대로 활용.

| 테이블 | 컬럼 | 용도 |
|--------|------|------|
| `atch_file_m` | `atch_file_no` | 파일 ID |
| | `atch_file_nm` | 파일명 (확장자 → MIME 추출) |
| | `atch_file_url_addr` | **S3 prefix** 저장 (예: `kim/abc-123/42/`) |
| | `atch_file_tokn_ecnt` | 파싱 후 총 토큰 수 |
| | audit 컬럼 | 그대로 |
| `chtb_msg_atch_file_d` | `chtb_tlk_id` + `atch_file_no` | 대화-파일 N:N 매핑 |
| `chtb_msg_d` | `atch_file_no` (이미 존재) | 메시지별 첨부 (사용 안 해도 무방) |

**파생 정보 derive 방법**:
- MIME → `mimetypes.guess_type(atch_file_nm)`
- 파일 크기 → S3 `head_object()` 의 `ContentLength`
- 페이지 수 → 파싱 메타 (안 저장)
- 파싱 상태 → S3에 `chunks.jsonl` 존재 여부
- 다운로드 URL → S3 prefix → presigned URL 즉시 생성

---

## 4. S3 버킷 구조

**버킷**: `wellbot-014498622157-ap-northeast-2-an` (ap-northeast-2)

```
s3://wellbot-014498622157-ap-northeast-2-an/
└── {emp_no}/
    └── {smry_id}/
        └── {file_no}/
            ├── original.{ext}     ← 원본 파일
            ├── chunks.jsonl       ← {"seq": 0, "text": "...", "tokens": 950}
            └── index.faiss        ← FAISS 직렬화 인덱스
```

### 버킷 설정

| 항목 | 설정 |
|------|------|
| Region | `ap-northeast-2` |
| Server-Side Encryption | SSE-S3 (Amazon S3 managed keys) |
| Block all public access | ✅ ON |
| Lifecycle Rule | 미완료 multipart upload 7일 후 자동 삭제 (권장) |
| CORS | ❌ 불필요 (서버 프록시 방식) |
| IAM 권한 | FullAccess (부여 완료) |

### AWS 자격증명

- 환경변수 기반 인증 (Bedrock 과 동일)
- `.env` 에는 `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` 를 별도 저장하지 않음
- boto3 가 시스템 환경변수에서 자동 로드

---

## 5. `config/models.yaml` 변경

각 모델에 `supports_vision`, `supports_document` 플래그 추가:

```yaml
models:
  - name: "Claude Sonnet 4.5"
    # ...기존...
    supports_vision: true
    supports_document: true
  - name: "Claude Opus 4.6"
    # ...기존...
    supports_vision: true
    supports_document: true
  - name: "Amazon Nova Pro"
    # ...기존...
    supports_vision: true
    supports_document: true
  - name: "Amazon Nova Lite"
    # ...기존...
    supports_vision: true
    supports_document: true
```

`ModelConfig` dataclass 에 두 필드 추가 (default `False`).

---

## 6. 신규 파일 목록

```
wellbot/
├── services/
│   ├── storage_service.py      # S3 multipart upload/download/presigned URL
│   ├── file_parser.py          # DocumentParser Protocol + Local/Upstage/Hybrid 구현 + PDF 분할
│   ├── chunker.py              # 토큰 기반 청킹 (overlap 지원)
│   ├── embedding_service.py    # Bedrock Titan 임베딩 + FAISS 인덱스 빌드/검색/캐시
│   ├── attachment_service.py   # atch_file_m / 매핑 CRUD + 업로드 파이프라인 오케스트레이션
│   └── tool_executor.py        # Bedrock Tool Use 핸들러 (search_attachment)
├── components/
│   └── chat/
│       └── attachment_chip.py  # 첨부 파일 칩 UI
└── api/
    ├── __init__.py
    └── upload.py               # FastAPI custom route (@rx.api.post)
```

---

## 7. Phase 별 구현 계획

### Phase 1: 스토리지 & 파서 인프라

**목표**: 파일 → S3 + 텍스트 추출 백엔드 완성.

| # | 파일 | 작업 |
|---|------|------|
| 1-1 | `constants.py` | §2.2 설정값 추가 |
| 1-2 | `.env` | `S3_BUCKET_NAME`, `S3_REGION`, `UPSTAGE_API_KEY`, `UPSTAGE_API_URL` 추가 |
| 1-3 | `config/models.yaml` + `services/config.py` | `supports_vision`, `supports_document` 필드 추가 |
| 1-4 | `pyproject.toml` | `pdfplumber`, `python-docx`, `openpyxl`, `python-pptx`, `pypdf`, `faiss-cpu`, `numpy`, `httpx` 추가 |
| 1-5 | `services/storage_service.py` | `S3StorageService`: `upload_streaming`, `download_bytes`, `head_object`, `get_presigned_url`, `delete_prefix` |
| 1-6 | `services/file_parser.py` | `DocumentParser` Protocol, `LocalParser`, `UpstageParser`, `HybridParser`. 팩토리: `get_parser(mode)` |
| 1-7 | `services/file_parser.py` | PDF 분할 로직 (페이지 + 용량 기준, 재귀 분할) |

**검증**: 단위 테스트 — 각 파서에 샘플 파일 → 텍스트 추출 검증.

---

### Phase 2: 업로드 플로우

**목표**: 브라우저 → FastAPI → S3 → Reflex State 갱신까지 완성.

| # | 파일 | 작업 |
|---|------|------|
| 2-1 | `api/upload.py` | `@rx.api.post("/api/upload")`: JWT 검증, multipart 수신, 사이즈/타입/개수 가드, S3 streaming upload (원본만), `attachment_service.process_attachment()` 비동기 트리거, `{file_no, name, mime}` 응답 |
| 2-2 | `services/attachment_service.py` | `register_attachment(emp_no, smry_id, filename, file_size, s3_prefix)` → `atch_file_m` INSERT + `chtb_msg_atch_file_d` INSERT |
| 2-3 | `services/attachment_service.py` | `process_attachment(file_no)`: S3 다운로드 → 파싱 → 청킹 → 임베딩 → S3에 `chunks.jsonl` + `index.faiss` PUT → `atch_file_m.atch_file_tokn_ecnt` UPDATE |
| 2-4 | `state/chat_state.py` | `AttachmentInfo(BaseModel)`, `pending_attachments: list`, `add_attachment(info)`, `remove_attachment(file_no)` 이벤트 핸들러 |
| 2-5 | `state/chat_state.py` | `trigger_upload()` 이벤트: `rx.call_script` 으로 hidden file input + fetch POST `/api/upload` 호출 → 결과로 `add_attachment` 트리거 |
| 2-6 | `components/chat/input_bar.py` | `_plus_menu_popover` 의 "파일 추가" 항목에 `on_click=ChatState.trigger_upload` 연결 + 입력창 상단에 `pending_attachments` 칩 영역 |
| 2-7 | `components/chat/attachment_chip.py` | 파일명 + 아이콘 + X 삭제 버튼 + 파싱 진행 인디케이터 (로딩 스피너 / 체크) |

**검증**: PDF/DOCX/이미지 업로드 → S3 prefix 확인 → DB 행 확인 → chip UI 표시.

---

### Phase 3: 컨텍스트 주입 (메타만)

**목표**: 매 턴 system prompt 에 파일 메타 목록 주입 (~100 토큰).

| # | 파일 | 작업 |
|---|------|------|
| 3-1 | `services/attachment_service.py` | `get_conversation_attachments(smry_id)` → 파일 목록 (이름, 크기, MIME, 토큰 수) 반환 |
| 3-2 | `state/chat_state.py` `send_message()` | system prompt 빌드 시 메타 목록 append |
| 3-3 | `services/bedrock_client.py` `_build_messages()` | 이미지 첨부 시 `content` 배열에 `{"image": {...}}` block 추가. `supports_vision=False` 모델은 차단 |
| 3-4 | `state/chat_state.py` | 이미지 업로드 시 현재 모델 `supports_vision` 체크 → 미지원이면 경고 |

**주입 형식**:
```
{기존 시스템 프롬프트}

## 이 대화에 첨부된 파일
파일 내용이 필요하면 search_attachment 도구를 사용하세요.

1. 보고서.pdf (PDF, 12페이지, 3,250 토큰)
2. 조직도.xlsx (Excel, 3시트, 1,200 토큰)
```

---

### Phase 4: 메시지 영역 UI

**목표**: 대화 로드 시 메시지에 첨부 파일 표시 + 다운로드.

| # | 파일 | 작업 |
|---|------|------|
| 4-1 | `services/chat_service.py` | `get_conversation_messages()` 확장 — 메시지별 첨부 정보 JOIN |
| 4-2 | `state/chat_state.py` | `Message` 모델에 `attachments: list[AttachmentInfo]` 추가 |
| 4-3 | `components/chat/message_bubble.py` | 메시지 하단에 첨부 파일 카드 (아이콘 + 파일명 + 크기) |
| 4-4 | `state/chat_state.py` | `download_attachment(file_no)` → S3 presigned URL → `rx.redirect(url, external=True)` |
| 4-5 | `state/chat_state.py` | 대화 전환 시 첨부 정보 복원 |

---

### Phase 5: Tool Use 기반 검색

**목표**: LLM 이 `search_attachment` 도구 자율 호출 → FAISS 검색 → 청크 반환.

| # | 파일 | 작업 |
|---|------|------|
| 5-1 | `services/chunker.py` | `chunk_text(text, size=1000, overlap=200)` — 토큰 기반 청킹 |
| 5-2 | `services/embedding_service.py` | `embed_texts(texts) -> np.ndarray` (Bedrock Titan 배치 호출) |
| 5-3 | `services/embedding_service.py` | `FaissCache`: 대화 단위 LRU 메모리 캐시. `get_or_load(smry_id)` → S3에서 모든 파일 인덱스 다운로드 → 통합 인덱스 구축 |
| 5-4 | `services/embedding_service.py` | `search(smry_id, query, top_k)` → query 임베딩 → FAISS 검색 → 청크 + 출처 파일명 반환 |
| 5-5 | `services/tool_executor.py` | `ATTACHMENT_TOOL` spec 정의, `execute_tool(tool_name, tool_input, smry_id)` 디스패치 |
| 5-6 | `services/bedrock_client.py` | `stream_chat()` / `astream_chat()` 확장: `tool_config` 파라미터, `toolUse` 이벤트, `toolResult` 재호출 루프 |
| 5-7 | `state/chat_state.py` `send_message()` | Tool Use 루프: `toolUse` → 실행 → `toolResult` 메시지 추가 → 재호출 (최대 `TOOL_USE_MAX_ITERATIONS` 회) |

**Tool 정의**:
```python
ATTACHMENT_TOOL = {
    "toolSpec": {
        "name": "search_attachment",
        "description": "대화에 첨부된 파일에서 관련 내용을 검색합니다.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색 자연어 쿼리"},
                    "file_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "검색 대상 파일명. 빈 배열이면 전체",
                    },
                },
                "required": ["query"],
            }
        },
    }
}
```

**주의**: 업로드 시 청킹·임베딩·S3 PUT 까지 Phase 2 의 `process_attachment` 에서 수행. Phase 5 에서는 **검색 경로** 만 추가.

---

## 8. 의존성 변경

### `pyproject.toml` 추가
```toml
"pdfplumber>=0.11.0",
"python-docx>=1.1.0",
"openpyxl>=3.1.0",
"python-pptx>=1.0.0",
"pypdf>=4.0.0",
"faiss-cpu>=1.8.0",
"numpy>=1.26.0",
"httpx>=0.27.0",
```

### `.env` 추가
```
# S3 Attachments
S3_BUCKET_NAME=wellbot-014498622157-ap-northeast-2-an
S3_REGION=ap-northeast-2

# Upstage Document Parse (선택)
UPSTAGE_API_KEY=
UPSTAGE_API_URL=
```

AWS 자격증명은 시스템 환경변수 기반 (boto3 자동 로드).

---

## 9. 리스크 & 완화

| 레벨 | 리스크 | 완화 |
|------|-------|------|
| HIGH | Tool Use 무한 루프 | `TOOL_USE_MAX_ITERATIONS=3` 강제 |
| HIGH | Titan 임베딩 비용 | 파일당 1회만 호출, S3에 영속 → 재시작 무관 |
| MEDIUM | 스캔 PDF 빈 텍스트 | `FILE_PARSER_FALLBACK=True` 시 Upstage 자동 폴백 |
| MEDIUM | FAISS 메모리 누적 | LRU 캐시 (`FAISS_CACHE_MAX_CONVERSATIONS=10`), 대화당 ~8MB |
| MEDIUM | FastAPI route 인증 | 기존 `auth_service` JWT 검증 재사용 |
| MEDIUM | Reflex State ↔ API route 동기화 | 업로드 응답 후 `rx.call_script` 으로 Reflex 이벤트 트리거 |
| MEDIUM | 비-PDF 용량 초과 | 사용자에게 분할 후 재업로드 안내 (자동 분할 미지원) |
| LOW | S3 미완료 multipart | 버킷 Lifecycle 7일 자동 삭제 |
| LOW | 첫 검색 latency | S3 인덱스 다운로드 50-200ms (이후 메모리 캐시) |

---

## 10. 구현 순서 의존 그래프

```
Phase 1 ──────────────────────────────────────
  1-1 constants  ┐
  1-2 .env       ├─ 설정 먼저
  1-3 models.yaml│
  1-4 deps       ┘
  1-5 storage_service
  1-6 file_parser
  1-7 PDF 분할

Phase 2 ────────── (Phase 1 완료 후)
  2-2 register_attachment   ← Phase 1-5
  2-3 process_attachment    ← Phase 1-6
  2-1 api/upload.py         ← 위 두 개
  2-4 chat_state 상태
  2-5 trigger_upload        ← Phase 2-1
  2-6 input_bar 연결
  2-7 attachment_chip

Phase 3 ────────── (Phase 2 완료 후)
  3-1 get_conversation_attachments
  3-2 send_message 메타 주입 ← Phase 3-1
  3-3 bedrock_client 이미지 block
  3-4 vision 가드

Phase 4 ────────── (Phase 2 완료 후, Phase 3 와 병렬 가능)
  4-1 chat_service 확장
  4-2 Message 모델 확장
  4-3 message_bubble
  4-4 download_attachment
  4-5 대화 전환 복원

Phase 5 ────────── (Phase 2 + Phase 3 완료 후)
  5-1 chunker
  5-2 embed_texts
  5-3 FaissCache             ← Phase 5-1, 5-2, Phase 1-5
  5-4 search                 ← Phase 5-3
  5-5 tool_executor          ← Phase 5-4
  5-6 bedrock tool 루프      ← Phase 5-5
  5-7 send_message 통합      ← Phase 5-6
```

---

## 11. 테스트 계획

| Phase | 유형 | 대상 |
|-------|-----|------|
| 1 | Unit | 각 파서별 샘플 파일 → 텍스트 추출, S3 mock 업로드/다운로드 |
| 2 | Integration | `/api/upload` → S3 prefix + DB 확인, 가드 케이스 (사이즈/타입/개수 초과) |
| 3 | Integration | system prompt 메타 포함 확인, vision block 생성 확인 |
| 4 | E2E | 대화 로드 → 첨부 카드 → 다운로드 |
| 5 | Integration | 임베딩 + FAISS 검색 정확도, Tool Use 루프 (mock LLM) |
| 전체 | E2E | PDF 업로드 → 질문 → tool 호출 → 정확한 답변, 멀티 파일, 이미지 |

---

## 12. 미해결 이슈 (구현 중 확인)

| 항목 | 확인 방법 |
|------|---------|
| S3 연결 검증 | `aws s3 ls s3://wellbot-014498622157-ap-northeast-2-an/` 성공 확인 |
| Lifecycle rule | 미완료 multipart 7일 삭제 정책 설정 권장 (선택) |
| Upstage API 키 | Upstage 모드 사용 시 `.env` 에 설정 필요 (local 모드에서는 불필요) |

---

**승인 이력**:
- 2026-04-15: PRD 작성 및 최종 확정 (김채현)
