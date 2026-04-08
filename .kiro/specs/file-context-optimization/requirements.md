# 요구사항 문서: 파일 컨텍스트 최적화 (File Context Optimization)

## 소개

WellBot 챗봇의 파일 활용 시스템을 개선하여 Bedrock Converse API의 파일 크기/개수 제한을 극복하고, 대용량 파일 지원, 파일 영속성(대화 턴 간 유지), 선택적 주입(Agentic RAG) 기능을 구현한다. 현재 시스템은 파일이 단일 턴에서만 사용되고, Bedrock API 제한(ImageBlock 3.75MB, DocumentBlock 4.5MB)이 사용자에게 직접 노출되는 구조이다. 이를 개선하여 사용자에게는 시스템 설정 최대 파일 크기 외의 제한을 노출하지 않으면서, 내부적으로 API 제약을 우회하는 아키텍처로 전환한다.

## 용어 정의

- **WellBot**: Reflex 기반 사내 업무 AI 어시스턴트 챗봇 시스템
- **ChatState**: WellBot의 채팅 상태를 관리하는 Reflex State 클래스
- **Bedrock_Converse_API**: AWS Bedrock의 대화형 LLM 호출 API (ImageBlock 최대 3.75MB/20개, DocumentBlock 최대 4.5MB/5개 제한)
- **Upstage_DP**: Upstage Document Parse API. 문서를 마크다운 텍스트로 변환하는 외부 파싱 서비스 (100페이지 제한)
- **Session_Active_Files**: 대화 세션 동안 활성 상태로 유지되는 인메모리 파일 저장소. 파일 메타데이터(파일명, 파일 타입, 크기, 페이지 수), 로컬 디스크 저장 경로, 파싱된 텍스트를 포함한다. DB의 기존 AtchFileM 테이블과 ChtbMsgD.atch_file_no를 통해 대화별 파일을 연결한다
- **File_Storage**: 파일 바이트의 물리적 저장을 담당하는 추상 인터페이스. Protocol 기반으로 정의하며 로컬 파일시스템 구현체를 사용한다
- **File_Validator**: 업로드 파일의 확장자, 크기, 개수를 검증하는 모듈
- **Content_Block_Builder**: 첨부 파일을 Bedrock Converse API content block 형식으로 변환하는 모듈
- **Relevance_Checker**: 사용자 질문에 대해 파일 컨텍스트 주입 필요 여부를 판단하는 경량 LLM 호출 모듈. Claude Haiku 모델을 사용하며, 판단 불확실 시 주입하는 방향(false positive 허용)으로 동작한다
- **File_Chunker**: 대용량 문서를 청크 단위로 분할하는 모듈. 기본 청크 크기 1,000토큰, 오버랩 200토큰
- **Text_Injection**: 파일 내용을 Bedrock API의 텍스트 블록으로 변환하여 user 메시지에 삽입하는 방식. DocumentBlock/ImageBlock 크기 제한을 우회한다
- **Context_Budget**: 컨텍스트 윈도우에서 파일 컨텍스트에 할당된 토큰 예산 (전체의 30%)

## 요구사항

### 요구사항 1: 파일 영속성 — 세션 활성 파일 저장소

**사용자 스토리:** 개발자로서, 업로드한 파일이 대화 전체에서 유지되기를 원한다. 매 턴마다 파일을 다시 첨부하지 않고도 이전에 올린 파일을 참조할 수 있어야 한다.

#### 인수 조건

1. WHEN 사용자가 파일을 업로드하면, THE ChatState SHALL 해당 파일의 바이트를 File_Storage를 통해 로컬 디스크에 저장하고, 메타데이터(파일명, 저장 경로, 토큰 수)를 기존 AtchFileM 테이블에 등록한다. 파일 타입(classify_file로 런타임 추론), 크기, 페이지 수, 파싱된 텍스트 등 추가 메타데이터는 Session_Active_Files 인메모리 dict에 보관하여 대화 세션이 종료될 때까지 유지한다
2. WHEN 사용자가 메시지를 전송하면, THE ChatState SHALL Session_Active_Files를 초기화하지 않고 보존한다. 메시지와 파일의 연결은 ChtbMsgD.atch_file_no를 통해 DB에 기록한다
3. WHEN 사용자가 특정 파일을 명시적으로 제거하면, THE ChatState SHALL 해당 파일만 Session_Active_Files에서 삭제하고 나머지 파일은 유지한다
4. WHEN 사용자가 새 대화를 시작하면, THE ChatState SHALL 이전 대화의 Session_Active_Files를 초기화하고 빈 상태로 새 대화를 생성한다
5. WHEN 사용자가 기존 대화로 전환하면, THE ChatState SHALL ChtbMsgD JOIN AtchFileM으로 해당 대화의 파일 목록을 조회하고, 파일명에서 타입을 추론하며, 필요 시 File_Storage에서 바이트를 lazy-load하고 pdfplumber/python-pptx로 페이지 수를 재계산하여 Session_Active_Files를 복원한다
6. THE File_Storage SHALL Protocol 기반 추상 인터페이스(save, load, delete)로 정의되며, 로컬 파일시스템 구현체(LocalFileStorage)를 기본으로 사용한다

### 요구사항 2: Bedrock API 파일 크기 제한 우회 — 텍스트 주입 방식

**사용자 스토리:** 사용자로서, Bedrock API의 DocumentBlock 4.5MB 제한이나 ImageBlock 3.75MB 제한에 구애받지 않고 파일을 활용하고 싶다. 시스템이 설정한 최대 파일 크기 내에서 자유롭게 파일을 업로드할 수 있어야 한다.

#### 인수 조건

1. WHEN 문서 파일의 크기가 Bedrock DocumentBlock 제한(4.5MB)을 초과하면, THE Content_Block_Builder SHALL 해당 파일을 DocumentBlock 대신 텍스트 블록으로 변환하여 user 메시지에 삽입한다
2. WHEN 이미지 파일의 크기가 Bedrock ImageBlock 제한(3.75MB)을 초과하면, THE Content_Block_Builder SHALL Pillow 라이브러리를 사용하여 해당 이미지를 3.75MB 이하로 리사이즈(해상도 축소, JPEG 품질 85%)하여 ImageBlock으로 전송한다
3. THE File_Validator SHALL config.yaml에 정의된 단일 최대 파일 크기 설정값을 기준으로 업로드 가능 여부를 판단하고, Bedrock API의 개별 타입별 크기 제한을 사용자에게 노출하지 않는다
4. WHEN 문서 파일이 텍스트 주입 방식으로 변환되면, THE Content_Block_Builder SHALL 원본 파일명을 텍스트 블록 헤더에 포함하여 LLM이 파일 출처를 식별할 수 있게 한다
5. THE Content_Block_Builder SHALL Bedrock API의 요청당 파일 개수 제한(이미지 20개, 문서 5개)을 내부적으로 관리하되, 텍스트 주입 방식으로 변환된 파일은 DocumentBlock 개수에 포함하지 않는다. 텍스트 주입된 파일은 Context_Budget의 파일 컨텍스트 예산(30%)에서 토큰을 차감한다

### 요구사항 3: 대용량 문서 처리 — 크기 기반 전략 분기

**사용자 스토리:** 사용자로서, 50페이지 이상의 대용량 문서도 업로드하여 활용하고 싶다. 시스템이 문서 크기에 따라 적절한 처리 전략을 자동으로 선택해야 한다.

#### 인수 조건

1. WHEN 문서가 10페이지 이하(소형)이면, THE File_Chunker SHALL 전체 텍스트를 그대로 Session_Active_Files에 저장한다
2. WHEN 문서가 10페이지 초과 50페이지 이하(중형)이면, THE File_Chunker SHALL 문서를 청크 단위(1,000토큰, 200토큰 오버랩)로 분할하고 각 청크의 요약을 경량 LLM(Claude Haiku)으로 생성하여 Session_Active_Files에 저장한다
3. WHEN 문서가 50페이지 초과(대형)이면, THE File_Chunker SHALL 문서를 청크 단위(1,000토큰, 200토큰 오버랩)로 분할하고 Bedrock Titan Embeddings 모델로 벡터 임베딩을 생성하여 인메모리 벡터 저장소(FAISS)에 세션 단위로 저장한다
4. WHEN 문서의 페이지 수가 Upstage_DP의 100페이지 제한을 초과하면, THE File_Chunker SHALL 문서를 100페이지 이하의 청크로 분할하여 Upstage_DP에 순차적으로 요청하고 결과를 원본 페이지 순서대로 병합한다
5. WHEN PDF 파일이 업로드되면, THE File_Chunker SHALL pdfplumber 라이브러리로 페이지 수를 사전 확인하여 처리 전략(소형/중형/대형)과 Upstage_DP 분할 필요 여부를 판단한다
6. WHEN PPT/PPTX 파일이 업로드되면, THE File_Chunker SHALL python-pptx 라이브러리로 슬라이드 수를 사전 확인하여 처리 전략과 분할 필요 여부를 판단한다
7. IF Upstage_DP 호출이 실패하면, THEN THE File_Chunker SHALL 해당 청크를 최대 2회 재시도하고, 재시도 후에도 실패하면 대체 파싱 방법(Python 기반 로컬 파싱: pdfplumber, python-pptx)을 시도한다. 대체 파싱도 실패하면 실패한 청크 범위를 포함한 에러 메시지를 사용자에게 반환한다

### 요구사항 4: 선택적 파일 컨텍스트 주입 (Agentic RAG)

**사용자 스토리:** 사용자로서, 파일을 업로드해 두었더라도 파일 내용이 필요하지 않은 일반 질문에서는 불필요한 토큰 소비 없이 빠른 응답을 받고 싶다.

#### 인수 조건

1. WHILE Session_Active_Files에 파일이 존재하는 동안, THE Relevance_Checker SHALL 각 사용자 메시지에 대해 파일 컨텍스트 주입 필요 여부를 판단한다
2. WHEN Relevance_Checker가 파일 컨텍스트가 불필요하다고 판단하면, THE ChatState SHALL 파일 블록 없이 텍스트만으로 LLM을 호출한다
3. WHEN Relevance_Checker가 파일 컨텍스트가 필요하다고 판단하면, THE ChatState SHALL 관련 파일의 컨텍스트를 현재 user 메시지에만 주입하고 대화 이력의 과거 메시지에는 포함하지 않는다
4. WHEN 대형 문서(50페이지 초과)에 대해 파일 컨텍스트가 필요하다고 판단되면, THE ChatState SHALL FAISS 인메모리 벡터 저장소에서 사용자 질문과 코사인 유사도 기준 상위 k개 청크만 검색하여 주입한다
5. THE Relevance_Checker SHALL 파일 메타데이터(파일명, 파일 타입, 페이지 수)와 사용자 질문만을 입력으로 사용하여 판단하고, 파일 전체 내용을 판단 과정에 사용하지 않는다
6. THE Relevance_Checker SHALL Claude Haiku 모델을 사용하며, 판단 불확실 시 파일 컨텍스트를 주입하는 방향(false positive 허용)으로 동작한다. 판단 실패(API 오류 등) 시에도 기본적으로 파일 컨텍스트를 주입한다

### 요구사항 5: 컨텍스트 윈도우 예산 관리

**사용자 스토리:** 개발자로서, 파일 컨텍스트가 대화 이력이나 시스템 프롬프트의 공간을 과도하게 침범하지 않도록 토큰 예산을 체계적으로 관리하고 싶다.

#### 인수 조건

1. THE LLM_Service SHALL 컨텍스트 윈도우를 시스템 프롬프트(5%), 파일 컨텍스트(30%), 대화 이력(50%), 현재 질문(15%)으로 예산을 배분한다. 각 비율은 config.yaml에서 모델별로 오버라이드할 수 있다
2. WHEN 파일 컨텍스트의 토큰 수가 할당된 예산(컨텍스트 윈도우의 30%)을 초과하면, THE LLM_Service SHALL 파일 컨텍스트를 요약 또는 청크 선택을 통해 예산 이내로 축소한다
3. WHEN 파일 컨텍스트 축소 후에도 대화 이력이 예산을 초과하면, THE LLM_Service SHALL 기존 슬라이딩 윈도우 방식으로 오래된 이력부터 제거한다
4. THE LLM_Service SHALL 파일 컨텍스트를 대화 이력의 과거 메시지가 아닌 현재 user 메시지에만 포함하여 이력 트리밍 시 파일 컨텍스트가 손실되지 않도록 한다

### 요구사항 6: 파일 업로드 시스템 개선

**사용자 스토리:** 사용자로서, 파일 업로드 시 Bedrock API 제한에 의한 불필요한 에러 없이 시스템이 설정한 최대 크기 내에서 자유롭게 파일을 업로드하고 싶다.

#### 인수 조건

1. THE File_Validator SHALL config.yaml에 정의된 단일 최대 파일 크기 설정값을 기준으로 업로드 가능 여부를 판단한다
2. WHEN 파일 업로드가 성공하면, THE ChatState SHALL 업로드된 파일을 File_Storage에 저장하고 Session_Active_Files에 추가하여 UI에 활성 파일 목록으로 표시한다
3. WHEN 프레젠테이션 파일(PPT/PPTX)이 업로드되면, THE Upstage_DP SHALL 해당 파일을 마크다운 텍스트로 변환하고, 변환된 텍스트를 Session_Active_Files에 저장한다
4. IF 파일 업로드 중 파싱 오류가 발생하면, THEN THE ChatState SHALL 사용자에게 파싱 실패 사유를 포함한 에러 메시지를 표시하고, 해당 파일을 Session_Active_Files에 추가하지 않는다
5. THE base_input_bar SHALL Session_Active_Files에 등록된 활성 파일 목록을 항상 표시하고, 각 파일에 대해 개별 제거 기능을 제공한다
