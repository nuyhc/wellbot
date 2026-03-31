# 구현 계획: 파일 업로드 → LLM 전달

## 개요

사용자가 첨부한 이미지/문서 파일을 메모리에서 검증·변환하여 AWS Bedrock Converse API로 전달하는 파이프라인을 구현한다. FileValidator → ContentBlockBuilder → stream_converse 확장 순서로 점진적으로 구축하며, 각 단계마다 속성 기반 테스트로 정확성을 검증한다.

## Tasks

- [x] 1. FileValidator 모듈 생성
  - [x] 1.1 `wellbot/services/file_validator.py` 생성 — 상수 및 `classify_file`, `validate_file` 함수 구현
    - `IMAGE_EXTENSIONS`, `DOCUMENT_EXTENSIONS`, `IMAGE_MAX_SIZE`, `DOCUMENT_MAX_SIZE`, `IMAGE_MAX_COUNT`, `DOCUMENT_MAX_COUNT` 상수 정의
    - `classify_file(filename)` → `'image'` | `'document'` | `ValueError`
    - `validate_file(filename, file_size, current_image_count, current_document_count)` → `None` | `ValueError`
    - 에러 메시지는 설계 문서의 에러 처리 섹션에 정의된 문자열을 사용
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 7.1, 7.2, 7.3_

  - [ ]* 1.2 Property 1 속성 기반 테스트 — 파일 분류 정확성
    - **Property 1: 파일 분류 정확성**
    - Hypothesis로 임의의 파일명(이미지 확장자, 문서 확장자, 미지원 확장자)을 생성하여 `classify_file` 반환값 검증
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [ ]* 1.3 Property 2 속성 기반 테스트 — 크기 제한 검증
    - **Property 2: 크기 제한 검증**
    - Hypothesis로 임의의 파일 타입과 크기를 생성하여 `validate_file`의 크기 제한 동작 검증
    - **Validates: Requirements 3.1, 3.2**

  - [ ]* 1.4 Property 3 속성 기반 테스트 — 개수 제한 검증
    - **Property 3: 개수 제한 검증**
    - Hypothesis로 임의의 파일 타입과 현재 첨부 개수를 생성하여 `validate_file`의 개수 제한 동작 검증
    - **Validates: Requirements 3.3, 3.4**

  - [ ]* 1.5 FileValidator 단위 테스트
    - 에러 메시지 문자열 정확성 검증 (지원되지 않는 확장자, 크기 초과, 개수 초과)
    - 빈 파일명, 확장자 없는 파일명 엣지 케이스
    - jpg 확장자 분류 확인
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 2. ContentBlockBuilder 모듈 생성
  - [x] 2.1 `wellbot/services/content_block_builder.py` 생성 — `AttachedFile` 데이터클래스 및 `build_content_blocks` 함수 구현
    - `AttachedFile(filename, data, file_type)` 데이터클래스 정의
    - `build_content_blocks(files)` → `list[dict]` (ImageBlock / DocumentBlock 변환)
    - 이미지: `{"image": {"format": ext, "source": {"bytes": data}}}` 형식
    - 문서: `{"document": {"name": stem, "format": ext, "source": {"bytes": data}}}` 형식
    - jpg → jpeg 매핑 처리
    - 변환 실패 파일은 건너뛰고 나머지 반환
    - _Requirements: 4.1, 4.2, 7.4_

  - [ ]* 2.2 Property 4 속성 기반 테스트 — Content Block 변환 정확성
    - **Property 4: Content Block 변환 정확성**
    - Hypothesis로 임의의 AttachedFile을 생성하여 `build_content_blocks` 반환 블록의 키·포맷·바이트 검증
    - **Validates: Requirements 4.1, 4.2**

  - [ ]* 2.3 Property 8 속성 기반 테스트 — 부분 실패 시 나머지 파일 처리
    - **Property 8: 부분 실패 시 나머지 파일 처리**
    - Hypothesis로 정상/비정상 AttachedFile 혼합 목록을 생성하여 반환 블록 수가 정상 파일 수와 일치하는지 검증
    - **Validates: Requirements 7.4**

  - [ ]* 2.4 ContentBlockBuilder 단위 테스트
    - jpg → jpeg 매핑 확인
    - 빈 파일 목록 처리
    - 문서 블록의 name 필드에서 확장자 제거 확인
    - _Requirements: 4.1, 4.2_

- [x] 3. 체크포인트 — FileValidator 및 ContentBlockBuilder 검증
  - 모든 테스트를 실행하여 통과 확인, 문제가 있으면 사용자에게 질문

- [x] 4. ChatState 확장
  - [x] 4.1 `wellbot/state/chat.py` 수정 — `attached_files` 타입 변경 및 `_file_data`, `upload_error` 추가
    - `attached_files: list[str]` → `attached_files: list[dict]` (dict 구조: `{"filename": str, "file_type": str}`)
    - `_file_data: dict[str, bytes] = {}` 비직렬화 인스턴스 변수 추가
    - `upload_error: str = ""` 상태 변수 추가
    - _Requirements: 1.2_

  - [x] 4.2 `handle_upload` 메서드 수정 — FileValidator 연동 및 바이트 데이터 메모리 저장
    - 파일 바이트를 `await file.read()`로 메모리에서 읽기 (디스크 저장 없음)
    - `FileValidator.classify_file` / `validate_file` 호출하여 검증
    - 검증 성공 시 `attached_files`에 dict 추가, `_file_data`에 바이트 저장
    - 검증 실패 시 `upload_error`에 에러 메시지 설정
    - 중복 파일명 처리 (덮어쓰기)
    - _Requirements: 1.1, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 7.1, 7.2, 7.3_

  - [x] 4.3 `remove_file` 메서드 수정 — `_file_data`에서도 바이트 제거
    - `attached_files` 리스트와 `_file_data` 딕셔너리 모두에서 해당 파일 제거
    - _Requirements: 6.1_

  - [x] 4.4 `answer` 메서드 수정 — ContentBlockBuilder 연동 및 file_blocks 전달
    - 첨부 파일이 있으면 `AttachedFile` 목록 구성 후 `build_content_blocks` 호출
    - 문서만 첨부하고 텍스트가 비어있으면 기본 텍스트("첨부된 파일을 분석해주세요.") 삽입
    - `stream_converse`에 `file_blocks` 파라미터로 전달
    - finally 블록에서 `attached_files = []`, `_file_data = {}` 초기화
    - _Requirements: 4.3, 5.2, 5.3, 6.1_

- [x] 5. stream_converse 함수 확장
  - [x] 5.1 `wellbot/services/llm.py` 수정 — `file_blocks` 파라미터 추가 및 content 배열 구성
    - `file_blocks: list[dict] | None = None` 파라미터 추가
    - `file_blocks`가 전달되면 현재 user 메시지의 content 배열에 텍스트 블록 + 파일 블록 포함
    - `file_blocks`가 None이면 기존 동작 유지 (텍스트만)
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ]* 5.2 Property 5 속성 기반 테스트 — 문서 포함 시 텍스트 블록 필수
    - **Property 5: 문서 포함 시 텍스트 블록 필수**
    - 문서 블록이 포함된 경우 user 메시지 content 배열에 텍스트 블록이 반드시 존재하는지 검증
    - **Validates: Requirements 4.3**

  - [ ]* 5.3 Property 6 속성 기반 테스트 — 메시지 구조 정확성
    - **Property 6: 메시지 구조 정확성**
    - Hypothesis로 임의의 메시지와 file_blocks를 생성하여 content 배열 구조 검증
    - **Validates: Requirements 5.2, 5.3**

  - [ ]* 5.4 stream_converse 단위 테스트
    - file_blocks=None일 때 기존 동작과 동일한지 확인
    - 문서만 첨부 시 기본 텍스트 삽입 확인
    - _Requirements: 5.3_

- [x] 6. 체크포인트 — ChatState 및 stream_converse 검증
  - 모든 테스트를 실행하여 통과 확인, 문제가 있으면 사용자에게 질문

- [x] 7. UI 에러 메시지 표시
  - [x] 7.1 `wellbot/components/base_input_bar.py` 수정 — `upload_error` 인라인 표시
    - `ChatState.upload_error`가 비어있지 않으면 입력바 상단에 에러 메시지 표시
    - 에러 메시지 스타일: 빨간색 텍스트, 파일 칩 목록 위에 배치
    - `ChatState.attached_files`의 타입 변경에 맞춰 `_file_chip`과 `rx.foreach` 수정 (dict에서 filename 추출)
    - _Requirements: 7.1, 7.2, 7.3_

- [ ]* 7.2 Property 7 속성 기반 테스트 — 전송 후 메모리 정리
    - **Property 7: 전송 후 메모리 정리**
    - 첨부 파일이 있는 상태에서 메시지 전송 완료 후 `attached_files`가 빈 목록이고 `_file_data`가 빈 딕셔너리인지 검증
    - **Validates: Requirements 6.1**

- [x] 8. 최종 체크포인트 — 전체 통합 검증
  - 모든 테스트를 실행하여 통과 확인, 문제가 있으면 사용자에게 질문

## 참고

- `*` 표시된 태스크는 선택 사항이며 빠른 MVP를 위해 건너뛸 수 있습니다
- 각 태스크는 추적 가능성을 위해 구체적인 요구사항을 참조합니다
- 체크포인트에서 점진적 검증을 수행합니다
- 속성 기반 테스트는 Hypothesis 라이브러리를 사용하며 최소 100회 반복 실행합니다
- 단위 테스트는 속성 기반 테스트가 커버하지 않는 구체적 예시와 엣지 케이스를 보완합니다
