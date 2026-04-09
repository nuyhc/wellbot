# 요구사항 문서

## 소개

기존 스텁(stub) 응답 기반의 챗봇을 Amazon Bedrock API와 연동하여 실제 AI 응답을 제공하는 챗봇으로 확장한다. boto3의 Bedrock Runtime 클라이언트를 사용하며, ConverseStream API를 통한 스트리밍 응답을 지원한다. 대화 컨텍스트(이전 메시지)를 Bedrock에 전달하여 맥락 있는 대화를 가능하게 한다. 파일 첨부 기능은 이번 스펙에서 제외한다.

## 용어 정의

- **Bedrock_Client**: boto3를 통해 Amazon Bedrock Runtime API와 통신하는 클라이언트 모듈
- **Chat_State**: Reflex의 상태 관리 클래스로, 메시지 전송 및 AI 응답 처리를 담당함 (기존 ChatState 확장)
- **Converse_Stream**: Amazon Bedrock Runtime의 ConverseStream API로, 모델 응답을 청크(chunk) 단위로 스트리밍 수신하는 방식
- **Model_ID**: Bedrock에서 사용할 파운데이션 모델(Foundation Model)의 식별자 (예: `anthropic.claude-sonnet-4-20250514`)
- **System_Prompt**: AI 모델에 전달되는 시스템 수준 지시문으로, 챗봇의 역할과 행동 방식을 정의함
- **Conversation_History**: 현재 대화 세션의 이전 메시지 목록으로, Bedrock API에 컨텍스트로 전달됨
- **Streaming_Chunk**: ConverseStream API가 반환하는 응답의 개별 텍스트 조각
- **Config_Manager**: 환경 변수 또는 설정 파일에서 Bedrock 관련 설정(리전, 모델 ID 등)을 로드하는 모듈

## 설계 결정 사항

| # | 항목 | 결정 |
|---|------|------|
| D1 | Bedrock API 방식 | ConverseStream API 사용 (스트리밍 응답) |
| D2 | AWS 인증 | boto3 기본 자격 증명 체인 사용 (환경 변수, AWS 프로파일 등) |
| D3 | 모델 선택 | 환경 변수로 모델 ID 설정, 기본값 제공 |
| D4 | 대화 컨텍스트 | 현재 대화의 전체 메시지 히스토리를 Bedrock에 전달 |
| D5 | 시스템 프롬프트 | 환경 변수 또는 설정으로 커스터마이징 가능 |
| D6 | 에러 처리 | 토스트 알림으로 사용자에게 에러 표시, 로깅 병행 |
| D7 | 스트리밍 UI | 청크 수신 시 실시간으로 메시지 버블에 텍스트 추가 |
| D8 | 파일 첨부 | 이번 스펙에서 제외 (후속 단계) |
| D9 | 의존성 | boto3 패키지를 pyproject.toml에 추가 |
| D10 | 대화 제목 생성 | 기존 방식 유지 (첫 번째 사용자 메시지 기반) |

## 요구사항

### 요구사항 1: Bedrock 클라이언트 모듈 구성

**사용자 스토리:** 개발자로서, Amazon Bedrock Runtime API와 통신하는 클라이언트 모듈을 원한다. 이를 통해 AI 모델과의 연동 로직을 상태 관리 코드와 분리할 수 있다.

#### 인수 조건

1. THE Bedrock_Client SHALL boto3의 bedrock-runtime 서비스 클라이언트를 생성하여 Amazon Bedrock API와 통신한다
2. THE Bedrock_Client SHALL AWS 리전 설정을 환경 변수(AWS_REGION 또는 AWS_DEFAULT_REGION)에서 읽어온다
3. THE Bedrock_Client SHALL boto3의 기본 자격 증명 체인(환경 변수, AWS 프로파일, IAM 역할 등)을 사용하여 인증한다
4. IF boto3 클라이언트 생성 시 자격 증명 오류가 발생하면, THEN THE Bedrock_Client SHALL 명확한 오류 메시지를 로깅하고 예외를 발생시킨다

### 요구사항 2: 환경 설정 관리

**사용자 스토리:** 개발자로서, Bedrock 관련 설정을 환경 변수로 관리하고 싶다. 이를 통해 배포 환경에 따라 모델이나 리전을 유연하게 변경할 수 있다.

#### 인수 조건

1. THE Config_Manager SHALL 모델 ID를 환경 변수(BEDROCK_MODEL_ID)에서 읽어오고, 환경 변수가 설정되지 않은 경우 기본값을 사용한다
2. THE Config_Manager SHALL 시스템 프롬프트를 환경 변수(BEDROCK_SYSTEM_PROMPT)에서 읽어오고, 환경 변수가 설정되지 않은 경우 기본 시스템 프롬프트를 사용한다
3. THE Config_Manager SHALL AWS 리전을 환경 변수(AWS_REGION)에서 읽어오고, 환경 변수가 설정되지 않은 경우 기본값 "us-east-1"을 사용한다
4. THE Config_Manager SHALL 최대 토큰 수를 환경 변수(BEDROCK_MAX_TOKENS)에서 읽어오고, 환경 변수가 설정되지 않은 경우 기본값 4096을 사용한다

### 요구사항 3: 스텁 응답 제거 및 Bedrock API 연동

**사용자 스토리:** 사용자로서, 실제 AI 모델의 응답을 받고 싶다. 이를 통해 의미 있는 대화를 나눌 수 있다.

#### 인수 조건

1. WHEN 사용자가 메시지를 전송하면, THE Chat_State SHALL STUB_RESPONSES 대신 Bedrock_Client를 통해 ConverseStream API를 호출하여 AI 응답을 생성한다
2. THE Chat_State SHALL 현재 대화의 Conversation_History를 Bedrock ConverseStream API의 messages 파라미터로 전달한다
3. THE Chat_State SHALL System_Prompt를 Bedrock ConverseStream API의 system 파라미터로 전달한다
4. THE Chat_State SHALL Config_Manager에서 읽어온 Model_ID를 Bedrock ConverseStream API의 modelId 파라미터로 전달한다
5. THE Chat_State SHALL Config_Manager에서 읽어온 최대 토큰 수를 Bedrock ConverseStream API의 inferenceConfig.maxTokens 파라미터로 전달한다
6. WHEN Bedrock API 호출이 완료되면, THE Chat_State SHALL AI 응답을 role "assistant"인 Message로 현재 Conversation에 추가한다

### 요구사항 4: 스트리밍 응답 처리

**사용자 스토리:** 사용자로서, AI 응답이 실시간으로 화면에 표시되길 원한다. 이를 통해 긴 응답도 기다리지 않고 바로 읽기 시작할 수 있다.

#### 인수 조건

1. WHEN ConverseStream API로부터 Streaming_Chunk를 수신하면, THE Chat_State SHALL 수신된 텍스트를 현재 AI 메시지의 content에 실시간으로 추가한다
2. WHILE 스트리밍 응답이 진행되는 동안, THE Chat_State SHALL is_loading 상태를 True로 유지한다
3. WHEN 스트리밍 응답의 모든 청크 수신이 완료되면, THE Chat_State SHALL is_loading 상태를 False로 설정한다
4. WHILE 스트리밍 응답이 진행되는 동안, THE Chat_State SHALL 각 청크 수신 시 UI 상태를 업데이트하여 사용자에게 실시간 텍스트 표시를 제공한다

### 요구사항 5: 에러 처리

**사용자 스토리:** 사용자로서, API 오류가 발생했을 때 명확한 안내를 받고 싶다. 이를 통해 문제 상황을 인지하고 적절히 대응할 수 있다.

#### 인수 조건

1. IF Bedrock API 호출 중 네트워크 오류가 발생하면, THEN THE Chat_State SHALL 토스트 알림으로 "네트워크 오류가 발생했습니다. 다시 시도해 주세요." 메시지를 표시한다
2. IF Bedrock API가 접근 거부(AccessDeniedException) 오류를 반환하면, THEN THE Chat_State SHALL 토스트 알림으로 "Bedrock 모델 접근 권한이 없습니다. AWS 설정을 확인해 주세요." 메시지를 표시한다
3. IF Bedrock API가 모델 미지원(ModelNotReadyException 또는 ValidationException) 오류를 반환하면, THEN THE Chat_State SHALL 토스트 알림으로 "모델을 사용할 수 없습니다. 모델 ID 설정을 확인해 주세요." 메시지를 표시한다
4. IF Bedrock API가 스로틀링(ThrottlingException) 오류를 반환하면, THEN THE Chat_State SHALL 토스트 알림으로 "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요." 메시지를 표시한다
5. IF Bedrock API 호출 중 예상치 못한 오류가 발생하면, THEN THE Chat_State SHALL 토스트 알림으로 일반 오류 메시지를 표시하고 오류 상세 내용을 로깅한다
6. IF 에러가 발생하면, THEN THE Chat_State SHALL is_loading 상태를 False로 설정하여 사용자가 다시 메시지를 전송할 수 있도록 한다
7. IF 스트리밍 도중 에러가 발생하면, THEN THE Chat_State SHALL 이미 수신된 부분 응답을 유지하고 에러 메시지를 토스트 알림으로 표시한다

### 요구사항 6: 의존성 및 프로젝트 설정

**사용자 스토리:** 개발자로서, Bedrock 연동에 필요한 패키지 의존성이 프로젝트에 올바르게 설정되길 원한다. 이를 통해 다른 개발자도 쉽게 환경을 구성할 수 있다.

#### 인수 조건

1. THE Chat_State SHALL pyproject.toml의 dependencies에 boto3 패키지를 추가한다
2. THE Chat_State SHALL 기존 STUB_RESPONSES 리스트와 관련 임포트(random, asyncio.sleep 지연 로직)를 제거한다
3. THE Bedrock_Client SHALL wellbot/services/ 디렉토리에 독립 모듈로 구현한다
