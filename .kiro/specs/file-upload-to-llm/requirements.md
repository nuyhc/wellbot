# 요구사항 문서

## 소개

WellBot 챗봇 애플리케이션에 파일 업로드 기능을 구현하여, 사용자가 첨부한 이미지 및 문서 파일을 AWS Bedrock Converse API를 통해 LLM에 전달하는 기능이다. 현재 UI에는 파일 업로드 컴포넌트가 존재하지만 파일명만 저장하고 실제 파일 저장 및 LLM 전달은 이루어지지 않는 상태이다.

## 용어 정의

- **ChatState**: Reflex 프레임워크의 상태 클래스로, 채팅 관련 상태(질문, 대화 이력, 첨부 파일 등)를 관리하는 컴포넌트
- **Converse_API**: AWS Bedrock의 대화형 API로, 텍스트·이미지·문서를 포함한 멀티모달 메시지를 LLM에 전달하는 인터페이스
- **ImageBlock**: Converse API에서 이미지 파일을 전달하기 위한 content block 형식 (base64 인코딩)
- **DocumentBlock**: Converse API에서 문서 파일을 전달하기 위한 content block 형식 (base64 인코딩)
- **File_Validator**: 업로드된 파일의 확장자, 크기, 개수를 검증하는 로직
- **Content_Block_Builder**: 첨부 파일을 Converse API가 요구하는 ImageBlock 또는 DocumentBlock 형식으로 변환하는 로직
- **Upload_Handler**: ChatState 내에서 파일 업로드를 처리하는 핸들러 메서드 (handle_upload)
- **지원_이미지_확장자**: png, jpeg, jpg, gif, webp
- **지원_문서_확장자**: pdf, csv, doc, docx, xls, xlsx, html, txt, md

## 요구사항

### 요구사항 1: 파일 메모리 처리

**사용자 스토리:** 사용자로서, 업로드한 파일이 메모리에서 직접 처리되기를 원한다. 그래야 디스크에 파일이 남지 않아 보안이 유지되고, 여러 사용자가 동시에 사용해도 파일 충돌이 발생하지 않는다.

#### 인수 조건

1. WHEN 사용자가 파일을 업로드하면, Upload_Handler는 해당 파일의 바이트 데이터를 메모리에서 읽어 ChatState에 저장해야 한다(SHALL).
2. WHEN 파일이 처리되면, ChatState는 파일명, 파일 바이트 데이터, 파일 타입(이미지/문서)을 attached_files 상태에 기록해야 한다(SHALL).
3. THE Upload_Handler는 파일을 디스크에 저장하지 않아야 한다(SHALL). 모든 파일 데이터는 세션 메모리 내에서만 유지된다.

### 요구사항 2: 파일 타입 분류

**사용자 스토리:** 시스템 개발자로서, 업로드된 파일이 이미지인지 문서인지 자동으로 분류되기를 원한다. 그래야 Converse API에 올바른 content block 형식으로 전달할 수 있다.

#### 인수 조건

1. WHEN 파일 확장자가 지원_이미지_확장자(png, jpeg, jpg, gif, webp) 중 하나이면, File_Validator는 해당 파일을 이미지 타입으로 분류해야 한다(SHALL).
2. WHEN 파일 확장자가 지원_문서_확장자(pdf, csv, doc, docx, xls, xlsx, html, txt, md) 중 하나이면, File_Validator는 해당 파일을 문서 타입으로 분류해야 한다(SHALL).
3. WHEN 파일 확장자가 지원_이미지_확장자에도 지원_문서_확장자에도 해당하지 않으면, File_Validator는 해당 파일을 거부하고 사용자에게 지원되지 않는 파일 형식임을 알려야 한다(SHALL).

### 요구사항 3: 파일 크기 및 개수 제한

**사용자 스토리:** 시스템 개발자로서, Bedrock Converse API의 제한을 초과하는 파일이 업로드 단계에서 사전 차단되기를 원한다. 그래야 API 호출 실패를 방지할 수 있다.

#### 인수 조건

1. WHEN 이미지 파일의 크기가 3.75MB를 초과하면, File_Validator는 해당 파일 업로드를 거부하고 크기 초과 메시지를 표시해야 한다(SHALL).
2. WHEN 문서 파일의 크기가 4.5MB를 초과하면, File_Validator는 해당 파일 업로드를 거부하고 크기 초과 메시지를 표시해야 한다(SHALL).
3. WHEN 첨부된 이미지 파일 수가 20개를 초과하면, File_Validator는 추가 이미지 업로드를 거부하고 개수 초과 메시지를 표시해야 한다(SHALL).
4. WHEN 첨부된 문서 파일 수가 5개를 초과하면, File_Validator는 추가 문서 업로드를 거부하고 개수 초과 메시지를 표시해야 한다(SHALL).

### 요구사항 4: 첨부 파일을 Converse API content block으로 변환

**사용자 스토리:** 시스템 개발자로서, 첨부된 파일이 Converse API가 요구하는 형식으로 변환되기를 원한다. 그래야 LLM이 파일 내용을 이해할 수 있다.

#### 인수 조건

1. WHEN 이미지 타입 파일이 첨부되면, Content_Block_Builder는 해당 파일을 base64로 인코딩하여 ImageBlock 형식(`{"image": {"format": "<확장자>", "source": {"bytes": <base64_bytes>}}}`)으로 변환해야 한다(SHALL).
2. WHEN 문서 타입 파일이 첨부되면, Content_Block_Builder는 해당 파일을 base64로 인코딩하여 DocumentBlock 형식(`{"document": {"name": "<파일명>", "format": "<확장자>", "source": {"bytes": <base64_bytes>}}}`)으로 변환해야 한다(SHALL).
3. WHEN 문서 타입 파일이 첨부된 메시지를 전송하면, Content_Block_Builder는 반드시 텍스트 content block을 함께 포함해야 한다(SHALL).
4. THE Content_Block_Builder는 모든 첨부 파일 content block을 role이 "user"인 메시지에만 포함해야 한다(SHALL).

### 요구사항 5: stream_converse 함수에 파일 content block 전달

**사용자 스토리:** 시스템 개발자로서, stream_converse 함수가 파일 content block을 받아 API 요청에 포함시키기를 원한다. 그래야 LLM이 파일과 텍스트를 함께 처리할 수 있다.

#### 인수 조건

1. THE stream_converse 함수는 파일 content block 목록을 파라미터로 받을 수 있어야 한다(SHALL).
2. WHEN 파일 content block이 전달되면, stream_converse 함수는 현재 사용자 메시지의 content 배열에 텍스트 block과 함께 파일 content block을 포함해야 한다(SHALL).
3. WHEN 파일 content block이 전달되지 않으면, stream_converse 함수는 기존과 동일하게 텍스트만 포함한 메시지를 전송해야 한다(SHALL).

### 요구사항 6: 전송 후 정리

**사용자 스토리:** 사용자로서, 메시지 전송 후 첨부 파일 목록이 초기화되기를 원한다. 그래야 다음 메시지에 이전 파일이 중복 전달되지 않는다.

#### 인수 조건

1. WHEN 메시지 전송이 완료되면(성공 또는 실패), ChatState는 attached_files 상태를 빈 목록으로 초기화하여 파일 바이트 데이터를 메모리에서 해제해야 한다(SHALL).

### 요구사항 7: 에러 처리

**사용자 스토리:** 사용자로서, 파일 업로드나 LLM 전달 과정에서 오류가 발생하면 명확한 에러 메시지를 받기를 원한다. 그래야 문제를 이해하고 대응할 수 있다.

#### 인수 조건

1. IF 지원되지 않는 파일 확장자의 파일이 업로드되면, THEN Upload_Handler는 "지원되지 않는 파일 형식입니다. 지원 형식: png, jpeg, jpg, gif, webp, pdf, csv, doc, docx, xls, xlsx, html, txt, md"라는 메시지를 표시해야 한다(SHALL).
2. IF 파일 크기가 제한을 초과하면, THEN Upload_Handler는 파일 타입별 최대 크기를 포함한 에러 메시지를 표시해야 한다(SHALL).
3. IF 파일 개수가 제한을 초과하면, THEN Upload_Handler는 파일 타입별 최대 개수를 포함한 에러 메시지를 표시해야 한다(SHALL).
4. IF 파일 읽기 또는 base64 인코딩 과정에서 오류가 발생하면, THEN Content_Block_Builder는 해당 파일을 건너뛰고 나머지 파일만 전달하며 사용자에게 오류를 알려야 한다(SHALL).
