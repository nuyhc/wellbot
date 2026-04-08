# 구현 계획: 파일 컨텍스트 최적화 (File Context Optimization)

## 개요

WellBot의 파일 활용 시스템을 세션 기반 영속 파일 관리 시스템으로 전환한다. config.yaml 설정 추가 → 서비스 레이어 신규 모듈 생성 → 기존 모듈 확장 → ChatState 통합 → UI 업데이트 순서로 점진적으로 구현한다. 각 단계는 이전 단계의 결과물 위에 빌드되며, 고아 코드 없이 통합된다.

## 작업 목록

- [ ] 1. 프로젝트 설정 및 config.yaml 확장
  - [ ] 1.1 의존성 추가 및 config.yaml 확장
    - `pyproject.toml`에 Pillow, pdfplumber, python-pptx, faiss-cpu 의존성 추가
    - `pyproject.toml` dev-dependencies에 hypothesis 추가
    - `config.yaml`에 `file_upload` 섹션 추가 (`max_file_size`, `max_file_count`, `upload_dir`)
    - `config.yaml`에 `context_budget` 섹션 추가 (`system_ratio`, `file_ratio`, `history_ratio`, `question_ratio`)
    - `config.yaml`에 `vector_store` 섹션 추가 (`default_k`, `retention_days`)
    - _요구사항: 2.3, 5.1, 6.1_
  - [ ] 1.2 config loader 확장
    - `wellbot/config/loader.py`에 `get_file_upload_config()`, `get_context_budget_config()`, `get_vector_store_config()` 함수 추가
    - 모델별 `context_budget` 오버라이드 로딩 지원
    - _요구사항: 5.1, 6.1_

- [ ] 2. FileStorage 서비스 구현
  - [ ] 2.1 FileStorage Protocol 및 LocalFileStorage 구현
    - `wellbot/services/file_storage.py` 신규 생성
    - `FileStorage` Protocol 정의 (save, load, delete)
    - `LocalFileStorage` 구현체: `{upload_dir}/{session_id}/{filename}` 경로에 저장 (`upload_dir`은 config.yaml `file_upload.upload_dir`에서 로드)
    - 디렉토리 자동 생성, 파일 읽기/쓰기/삭제 구현
    - _요구사항: 1.6_
  - [ ]* 2.2 FileStorage save/load 라운드트립 속성 테스트
    - **Property 2: FileStorage save/load 라운드트립**
    - **검증 대상: 요구사항 1.6**

- [ ] 3. FileValidator 개선 — config.yaml 기반 통합 검증
  - [ ] 3.1 FileValidator를 config.yaml 기반으로 리팩토링
    - `wellbot/services/file_validator.py` 수정
    - 기존 타입별 크기 제한(IMAGE_MAX_SIZE, DOCUMENT_MAX_SIZE 등) 제거
    - config.yaml의 `max_file_size`, `max_file_count` 기반 단일 검증으로 변경
    - `validate_file()` 시그니처 변경: `max_file_size`, `max_file_count` 파라미터 추가
    - Bedrock API 개별 타입별 크기 제한을 사용자에게 노출하지 않음
    - _요구사항: 2.3, 6.1_
  - [ ]* 3.2 config.yaml 기반 통합 파일 크기 검증 속성 테스트
    - **Property 5: config.yaml 기반 통합 파일 크기 검증**
    - **검증 대상: 요구사항 2.3, 6.1**

- [ ] 4. ContentBlockBuilder 확장 — 텍스트 주입 및 이미지 리사이즈
  - [ ] 4.1 이미지 리사이즈 함수 구현
    - `wellbot/services/content_block_builder.py`에 `_resize_image()` 함수 추가
    - Pillow 라이브러리로 해상도 축소 + JPEG 품질 85% 적용
    - 3.75MB 초과 이미지를 3.75MB 이하로 리사이즈
    - _요구사항: 2.2_
  - [ ]* 4.2 이미지 리사이즈 크기 보장 속성 테스트
    - **Property 4: 이미지 리사이즈 크기 보장**
    - **검증 대상: 요구사항 2.2**
  - [ ] 4.3 build_content_blocks 확장 — 텍스트 주입 방식
    - 문서 크기 > 4.5MB → DocumentBlock 대신 텍스트 블록으로 변환
    - 이미지 크기 > 3.75MB → `_resize_image()`로 리사이즈 후 ImageBlock
    - 텍스트 주입 시 원본 파일명을 헤더에 포함 (`[첨부 파일: {filename}]`)
    - 텍스트 주입된 파일은 DocumentBlock 개수에 미포함
    - 텍스트 주입된 파일의 토큰 수를 반환하여 Context_Budget 파일 예산(30%)에서 차감할 수 있게 함
    - `file_contexts` 파라미터 추가로 파싱된 텍스트 컨텍스트 수신
    - _요구사항: 2.1, 2.4, 2.5_
  - [ ]* 4.4 문서 크기 기반 블록 타입 분기 속성 테스트
    - **Property 3: 문서 크기 기반 블록 타입 분기**
    - **검증 대상: 요구사항 2.1**
  - [ ]* 4.5 텍스트 주입 블록 파일명 헤더 포함 속성 테스트
    - **Property 6: 텍스트 주입 블록에 파일명 헤더 포함**
    - **검증 대상: 요구사항 2.4**
  - [ ]* 4.6 텍스트 주입 파일 DocumentBlock 개수 제외 속성 테스트
    - **Property 7: 텍스트 주입 파일은 DocumentBlock 개수에서 제외**
    - **검증 대상: 요구사항 2.5**

- [ ] 5. 체크포인트 — 기반 서비스 검증
  - 모든 테스트가 통과하는지 확인하고, 질문이 있으면 사용자에게 문의한다.

- [ ] 6. Upstage DP 확장 — 100페이지 분할 처리
  - [ ] 6.1 Upstage DP 100페이지 분할 파싱 구현
    - `wellbot/services/upstage_dp.py` 수정
    - `parse_document_chunked()` 함수 추가: 100페이지 초과 시 분할하여 순차 요청 후 결과 병합
    - 청크별 최대 2회 재시도, 실패 시 대체 파싱(pdfplumber/python-pptx) 시도
    - 대체 파싱도 실패 시 실패한 청크 범위 포함 에러 메시지 반환
    - 분할 로직을 `upstage_dp.py` 안에 캡슐화하여 FileChunker는 단순 위임만 수행
    - _요구사항: 3.4, 3.7_
  - [ ]* 6.2 Upstage DP 페이지 분할 계획 완전성 속성 테스트
    - **Property 9: Upstage DP 페이지 분할 계획의 완전성**
    - **검증 대상: 요구사항 3.4**

- [ ] 7. FileChunker 서비스 구현
  - [ ] 7.1 FileChunker 핵심 로직 구현
    - `wellbot/services/file_chunker.py` 신규 생성
    - `DocumentSize` enum, `ChunkResult` dataclass 정의
    - `_count_pages()`: pdfplumber(PDF), python-pptx(PPT/PPTX)로 페이지 수 확인
    - `_chunk_text()`: 1,000토큰 청크, 200토큰 오버랩으로 텍스트 분할
    - `_split_and_parse()`: `upstage_dp.parse_document_chunked()`에 위임 (분할 로직은 upstage_dp.py에 캡슐화됨)
    - _요구사항: 3.1, 3.2, 3.4, 3.5, 3.6_
  - [ ]* 7.2 청크 분할 크기 및 오버랩 정확성 속성 테스트
    - **Property 8: 청크 분할 크기 및 오버랩 정확성**
    - **검증 대상: 요구사항 3.2**
  - [ ] 7.3 FileChunker 크기 기반 전략 분기 구현
    - `process_document()` 메서드 구현
    - 소형(≤10페이지): 전체 텍스트 그대로 저장
    - 중형(11~50페이지): 청크 분할 + Claude Haiku 요약 생성
    - 대형(>50페이지): 청크 분할 + Titan Embeddings → VectorStore 인덱싱
    - _요구사항: 3.1, 3.2, 3.3_
  - [ ]* 7.4 FileChunker 단위 테스트
    - PDF/PPTX 페이지 수 확인 테스트
    - 소형 문서 전체 텍스트 저장 테스트
    - Upstage DP 실패 시 재시도 + 대체 파싱 테스트
    - _요구사항: 3.1, 3.5, 3.6, 3.7_

- [ ] 8. VectorStore 서비스 구현
  - [ ] 8.1 VectorStore Protocol 및 FaissVectorStore 구현
    - `wellbot/services/vector_store.py` 신규 생성
    - `VectorStore` Protocol 정의 (index, search, delete)
    - `VectorStoreEntry` dataclass (session_id, filename, chunks, index, created_at)
    - `FaissVectorStore` 구현: FAISS 인메모리 인덱싱, 코사인 유사도 검색
    - 검색 시 상위 k개 반환 (k는 config.yaml `vector_store.default_k`에서 로드, 기본값 5)
    - Bedrock Titan Embeddings 호출로 벡터 생성
    - _요구사항: 3.3, 4.4_
  - [ ] 8.2 VectorStore 30일 보관 및 cleanup 구현
    - `VectorStoreEntry.created_at` 기반 만료 판단 (config.yaml `vector_store.retention_days`, 기본 30일)
    - `cleanup_expired()`: 만료 엔트리 삭제 후 삭제 수 반환
    - cleanup 트리거: 앱 시작 시 1회 + `handle_upload()` 호출 시마다 체크 (마지막 cleanup 후 24시간 경과 시 실행)
    - _요구사항: design 결정_
  - [ ]* 8.3 VectorStore 만료 cleanup 단위 테스트
    - 30일 경과 엔트리 삭제 테스트
    - 미만료 엔트리 유지 테스트
    - _요구사항: design 결정_

- [ ] 9. 체크포인트 — 문서 처리 파이프라인 검증
  - 모든 테스트가 통과하는지 확인하고, 질문이 있으면 사용자에게 문의한다.

- [ ] 10. RelevanceChecker 서비스 구현
  - [ ] 10.1 RelevanceChecker 구현
    - `wellbot/services/relevance_checker.py` 신규 생성
    - `FileMetadata` dataclass 정의 (filename, file_type, page_count)
    - `check_relevance()`: Claude Haiku로 파일 컨텍스트 주입 필요 여부 판단
    - 파일 메타데이터(파일명, 타입, 페이지 수)와 질문만 입력으로 사용
    - 판단 불확실 시 주입 방향(false positive 허용)
    - API 오류 시 모든 파일 반환 (기본 주입)
    - _요구사항: 4.1, 4.5, 4.6_
  - [ ]* 10.2 RelevanceChecker 단위 테스트
    - API 오류 시 기본 주입 동작 테스트
    - 판단 결과에 따른 분기 테스트
    - _요구사항: 4.1, 4.2, 4.6_

- [ ] 11. LLM 서비스 확장 — 컨텍스트 예산 관리
  - [ ] 11.1 ContextBudget 및 예산 관리 함수 구현
    - `wellbot/services/llm.py`에 `ContextBudget` dataclass 추가
    - `allocate_budget()`: 컨텍스트 윈도우를 시스템(5%), 파일(30%), 이력(50%), 질문(15%)으로 배분
    - `trim_file_context()`: 파일 컨텍스트를 예산 이내로 축소. 텍스트 주입된 파일의 토큰도 파일 예산(30%)에서 차감
    - 기존 `trim_history()` 수정: 파일 컨텍스트 예산을 고려한 이력 트리밍
    - `stream_converse()` 수정: 파일 컨텍스트를 현재 user 메시지에만 포함
    - _요구사항: 2.5, 5.1, 5.2, 5.3, 5.4_
  - [ ]* 11.2 컨텍스트 예산 배분 합계 보존 속성 테스트
    - **Property 11: 컨텍스트 예산 배분 합계 보존**
    - **검증 대상: 요구사항 5.1**
  - [ ]* 11.3 파일 컨텍스트 예산 내 축소 보장 속성 테스트
    - **Property 12: 파일 컨텍스트 예산 내 축소 보장**
    - **검증 대상: 요구사항 5.2**
  - [ ]* 11.4 대화 이력 트리밍 예산 준수 속성 테스트
    - **Property 13: 대화 이력 트리밍 예산 준수**
    - **검증 대상: 요구사항 5.3**
  - [ ]* 11.5 파일 컨텍스트 현재 메시지 전용 주입 속성 테스트
    - **Property 10: 파일 컨텍스트는 현재 메시지에만 주입**
    - **검증 대상: 요구사항 4.3, 5.4**

- [ ] 12. 체크포인트 — 서비스 레이어 전체 검증
  - 모든 테스트가 통과하는지 확인하고, 질문이 있으면 사용자에게 문의한다.

- [ ] 13. ChatState 확장 — 세션 활성 파일 관리
  - [ ] 13.1 session_active_files 상태 및 handle_upload 확장
    - `wellbot/state/chat.py`에 `session_active_files: list[dict]` 상태 추가
    - `handle_upload()` 수정: FileValidator(config.yaml 기준) → FileStorage.save() → AtchFileM INSERT(PK=int(time.time_ns())) → FileChunker.process_document() → session_active_files 등록
    - 기존 `attached_files`, `_file_data`는 업로드 중간 버퍼로만 사용
    - 기존 `remove_file()` → `remove_active_file(filename)`으로 변경: session_active_files에서 특정 파일만 제거
    - _요구사항: 1.1, 1.3, 6.2, 6.3, 6.4_
  - [ ] 13.2 answer() 확장 — 파일 영속성 및 선택적 주입
    - `answer()` 수정: session_active_files를 초기화하지 않고 보존
    - 활성 파일당 별도 ChtbMsgD row INSERT (atch_file_no 연결)
      → 동일 (CHTB_TLK_ID, CHTB_TLK_SEQ)에 파일 수만큼 row 생성
    - RelevanceChecker로 파일 컨텍스트 주입 여부 판단
    - 관련 파일만 ContentBlockBuilder로 블록 생성
    - 대형 문서는 VectorStore에서 상위 k개 청크 검색하여 주입 (k는 config.yaml에서 로드)
    - ContextBudget으로 파일 컨텍스트 예산 관리 (텍스트 주입 토큰 포함)
    - _요구사항: 1.2, 2.5, 4.1, 4.2, 4.3, 4.4_
  - [ ] 13.3 new_chat 확장
    - `new_chat()` 수정: session_active_files 초기화 (FAISS 인덱스 참조도 정리)
    - _요구사항: 1.4_
  - [ ] 13.4 switch_conversation — DB 조회 및 메타데이터 복원
    - `switch_conversation()` 수정: ChtbMsgD JOIN AtchFileM 쿼리로 해당 대화의 파일 목록 조회
    - 메시지 조회 시 `(CHTB_TLK_ID, CHTB_TLK_SEQ)` 기준 그룹핑으로 파일당 별도 row 중복 처리
    - 각 파일에 대해 classify_file(파일명)으로 file_type 추론
    - FileStorage.load()로 바이트 lazy-load, pdfplumber/python-pptx로 페이지 수 재계산
    - _요구사항: 1.5_
  - [ ] 13.5 switch_conversation — 대형 문서 VectorStore 복원
    - 대화 전환 시 대형 문서(>50페이지)의 VectorStore 인덱스 복원
    - VectorStore에서 기존 인덱스 조회 (30일 이내면 캐시 히트)
    - 만료 또는 미존재 시 FileChunker로 재처리 → VectorStore 재구축
    - _요구사항: 1.5, design 결정_
  - [ ]* 13.6 파일 제거 시 선택적 삭제 속성 테스트
    - **Property 1: 파일 제거 시 선택적 삭제**
    - **검증 대상: 요구사항 1.3**
  - [ ]* 13.7 ChatState 단위 테스트
    - answer() 후 session_active_files 보존 테스트
    - answer() 시 파일당 별도 ChtbMsgD row INSERT 확인 테스트
    - 메시지 조회 시 (CHTB_TLK_ID, CHTB_TLK_SEQ) 그룹핑 중복 처리 테스트
    - new_chat() 시 session_active_files 초기화 테스트
    - switch_conversation 시 파일 복원 테스트 (소형/중형/대형)
    - 파싱 오류 시 에러 메시지 + session_active_files 미추가 테스트
    - _요구사항: 1.2, 1.4, 1.5, 6.4_
  - [ ]* 13.8 PK 충돌 방지 테스트
    - time.time_ns() 기반 PK 생성 시 동시 업로드 시나리오 테스트
    - _요구사항: design 결정_

- [ ] 14. UI 업데이트 — 활성 파일 목록 표시
  - [ ] 14.1 base_input_bar 확장
    - `wellbot/components/base_input_bar.py` 수정
    - session_active_files 기반 영구 활성 파일 목록 표시
    - 각 파일에 개별 제거 버튼 (`remove_active_file(filename)` 호출)
    - 기존 `remove_file()` 호출부를 `remove_active_file()`로 변경
    - 기존 attached_files 칩 목록은 업로드 중간 상태 표시용으로 유지
    - _요구사항: 6.5_

- [ ] 15. 통합 및 최종 검증
  - [ ] 15.1 전체 흐름 통합 와이어링
    - ChatState에서 모든 서비스 모듈 연결 확인
    - 파일 업로드 → FileStorage 저장 → AtchFileM 등록 → session_active_files 등록 전체 흐름 검증
    - 대화 전환 시 파일 복원 흐름 검증 (소형/중형/대형 각각)
    - _요구사항: 1.1, 1.5_
  - [ ]* 15.2 통합 테스트 작성
    - 파일 업로드 → 저장 → 등록 전체 흐름 통합 테스트
    - 다중 파일 업로드 → 메시지 전송 → 파일당 별도 row → 조회 그룹핑 통합 테스트
    - 대화 전환 시 대형 문서 VectorStore 캐시 히트/재구축 통합 테스트
    - 대형 문서 FAISS 인덱싱 + 검색 통합 테스트
    - PPT/PPTX Upstage DP 변환 + session_active_files 저장 통합 테스트
    - _요구사항: 1.1, 1.2, 1.5, 3.3, 4.4, 6.3_

- [ ] 16. 최종 체크포인트 — 전체 테스트 통과 확인
  - 모든 테스트가 통과하는지 확인하고, 질문이 있으면 사용자에게 문의한다.

## 참고 사항

- `*` 표시된 작업은 선택 사항이며, 빠른 MVP를 위해 건너뛸 수 있습니다
- 각 작업은 특정 요구사항을 참조하여 추적 가능합니다
- 체크포인트에서 점진적 검증을 수행합니다
- 속성 테스트(Property-Based Test)는 설계 문서의 정확성 속성을 검증합니다
- 단위 테스트는 특정 예시와 엣지 케이스를 검증합니다
