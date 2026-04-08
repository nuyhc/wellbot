# 요구사항 문서

## 소개

AWS Bedrock 기반 AI 챗봇 웹 애플리케이션의 기본 UI를 Reflex 프레임워크로 구현한다. ChatGPT, Claude, Perplexity 스타일의 대화형 인터페이스를 제공하며, 이번 단계에서는 프론트엔드 UI 레이아웃과 기본 상호작용에 집중한다. 실제 Bedrock API 연동은 후속 단계에서 진행한다.

## 용어 정의

- **Chat_UI**: Reflex 프레임워크로 구현된 챗봇 웹 애플리케이션의 사용자 인터페이스
- **Message_Area**: 사용자와 AI 간의 대화 메시지가 표시되는 스크롤 가능한 영역
- **Input_Bar**: 사용자가 메시지를 입력하고 전송할 수 있는 하단 입력 영역
- **Sidebar**: 대화 목록과 새 대화 생성 버튼이 위치한 좌측 패널
- **Message_Bubble**: 개별 메시지를 감싸는 시각적 컨테이너로, 발신자(사용자/AI)에 따라 스타일이 다름
- **Conversation**: 사용자와 AI 간의 하나의 대화 세션으로, 여러 메시지로 구성됨
- **State_Manager**: Reflex의 상태 관리 클래스로, UI 상태와 메시지 데이터를 관리함
- **Login_Page**: 사용자가 이메일과 비밀번호를 입력하여 인증을 수행하는 페이지
- **User_Profile**: Sidebar 하단에 표시되는 로그인된 사용자의 프로필 정보 영역(이름, 이메일 등)
- **Auth_State**: 사용자 인증 상태를 관리하는 Reflex State 클래스로, 로그인/로그아웃 처리를 담당함

## 설계 결정 사항

| # | 항목 | 결정 |
|---|------|------|
| D1 | 인증 백엔드 | MySQL DB 기반 인증 (bcrypt 해싱 + JWT 세션) |
| D2 | 대화 데이터 영속성 | 이번 단계는 메모리 only, 후속 단계에서 DB 연동 |
| D3 | Sidebar 모바일 UX | 슬라이드 방식 + 고정/숨기기 토글 |
| D4 | 멀티라인 입력 | Shift+Enter로 줄바꿈, Enter로 전송 |
| D5 | 대화 제목 생성 | 첫 번째 사용자 메시지 기반 |
| D6 | 스텁 응답 지연 | 랜덤 0.5~3초 |
| D7 | 에러 상태 UI | 상단 토스트 알림 |
| D8 | 접근성(a11y) | 후속 단계에서 처리 |
| D9 | 마크다운 렌더링 | AI 응답에 마크다운 렌더링 지원 |
| D10 | 대화 검색 | 후속 단계에서 처리 |
| D11 | 대화 이름 변경 | 후속 단계에서 처리 |

## 요구사항

### 요구사항 1: 전체 레이아웃 구성

**사용자 스토리:** 개발자로서, ChatGPT/Claude 스타일의 레이아웃을 갖춘 웹 애플리케이션을 원한다. 이를 통해 사용자에게 익숙한 챗봇 경험을 제공할 수 있다.

#### 인수 조건

1. THE Chat_UI SHALL 좌측 Sidebar와 우측 메인 대화 영역으로 구성된 2단 레이아웃을 렌더링한다
2. THE Chat_UI SHALL 브라우저 뷰포트 전체 높이(100vh)를 사용하여 렌더링한다
3. WHEN 브라우저 창 너비가 768px 미만일 때, THE Sidebar SHALL 기본적으로 숨겨진 상태로 전환된다
4. WHEN 사용자가 모바일 메뉴 토글 버튼을 클릭하면, THE Sidebar SHALL 슬라이드 애니메이션으로 표시 상태를 토글한다
5. THE Sidebar SHALL 고정(pin) 및 숨기기(hide) 토글 기능을 제공한다

### 요구사항 2: 사이드바 기능

**사용자 스토리:** 사용자로서, 여러 대화를 관리할 수 있는 사이드바를 원한다. 이를 통해 이전 대화로 돌아가거나 새 대화를 시작할 수 있다.

#### 인수 조건

1. THE Sidebar SHALL "새 대화" 버튼을 상단에 표시한다
2. WHEN 사용자가 "새 대화" 버튼을 클릭하면, THE State_Manager SHALL 빈 메시지 목록을 가진 새 Conversation을 생성한다
3. THE Sidebar SHALL 기존 Conversation 목록을 시간 역순으로 표시한다 (제목은 첫 번째 사용자 메시지 기반으로 생성)
4. WHEN 사용자가 Conversation 목록의 항목을 클릭하면, THE Message_Area SHALL 해당 Conversation의 메시지를 표시한다
5. WHEN 사용자가 Conversation 항목의 삭제 버튼을 클릭하면, THE State_Manager SHALL 해당 Conversation을 목록에서 제거한다
6. THE Sidebar SHALL 하단 영역에 로그인된 사용자의 User_Profile(이름, 이메일)을 표시한다
7. WHEN 사용자가 User_Profile 영역의 로그아웃 버튼을 클릭하면, THE Auth_State SHALL 로그아웃을 수행하고 Login_Page로 리다이렉트한다

### 요구사항 3: 메시지 표시 영역

**사용자 스토리:** 사용자로서, 대화 내용을 명확하게 구분하여 볼 수 있는 메시지 영역을 원한다. 이를 통해 AI와의 대화 흐름을 쉽게 파악할 수 있다.

#### 인수 조건

1. THE Message_Area SHALL 사용자 메시지와 AI 메시지를 시각적으로 구분하여 표시한다 (AI 메시지는 마크다운 렌더링 지원)
2. THE Message_Bubble SHALL 사용자 메시지를 우측 정렬로, AI 메시지를 좌측 정렬로 표시한다
3. THE Message_Area SHALL 새 메시지가 추가될 때 자동으로 최하단으로 스크롤한다
4. WHEN Conversation에 메시지가 없을 때, THE Message_Area SHALL 환영 메시지 또는 시작 안내 문구를 표시한다
5. THE Message_Bubble SHALL 각 메시지의 발신자 아이콘(사용자/AI)을 표시한다

### 요구사항 4: 메시지 입력 및 전송

**사용자 스토리:** 사용자로서, 편리하게 메시지를 입력하고 전송할 수 있는 입력 영역을 원한다. 이를 통해 AI와 원활하게 대화할 수 있다.

#### 인수 조건

1. THE Input_Bar SHALL 메인 대화 영역 하단에 고정 배치된다
2. THE Input_Bar SHALL 텍스트 입력 필드와 전송 버튼을 포함한다
3. WHEN 사용자가 전송 버튼을 클릭하면, THE State_Manager SHALL 입력된 텍스트를 사용자 메시지로 현재 Conversation에 추가한다
4. WHEN 사용자가 Enter 키를 누르면, THE State_Manager SHALL 입력된 텍스트를 사용자 메시지로 현재 Conversation에 추가한다
5. WHEN 사용자가 Shift+Enter 키를 누르면, THE Input_Bar SHALL 텍스트에 줄바꿈을 삽입한다 (전송하지 않음)
6. WHEN 메시지가 전송된 후, THE Input_Bar SHALL 입력 필드를 빈 상태로 초기화한다
7. WHILE 입력 필드가 비어있는 상태에서, THE Input_Bar SHALL 전송 버튼을 비활성화 상태로 표시한다

### 요구사항 5: AI 응답 시뮬레이션 (스텁)

**사용자 스토리:** 개발자로서, Bedrock API 연동 전에 UI 동작을 검증할 수 있는 스텁 응답 기능을 원한다. 이를 통해 UI 개발과 API 연동을 독립적으로 진행할 수 있다.

#### 인수 조건

1. WHEN 사용자가 메시지를 전송하면, THE State_Manager SHALL 미리 정의된 스텁 응답을 AI 메시지로 생성한다
2. THE State_Manager SHALL 스텁 응답 생성 시 0.5~3초 범위의 랜덤 지연을 적용한다
3. WHILE AI 응답이 생성되는 동안, THE Message_Area SHALL 로딩 인디케이터를 표시한다
4. WHEN 스텁 응답이 완료되면, THE Message_Area SHALL 로딩 인디케이터를 제거하고 AI 메시지를 표시한다

### 요구사항 6: Reflex 프로젝트 초기 설정

**사용자 스토리:** 개발자로서, Reflex 프레임워크 기반의 올바른 프로젝트 구조를 원한다. 이를 통해 향후 기능 확장이 용이한 코드베이스를 유지할 수 있다.

#### 인수 조건

1. THE Chat_UI SHALL Reflex 프레임워크(reflex 패키지)를 사용하여 구현된다
2. THE Chat_UI SHALL pyproject.toml에 reflex 의존성을 명시한다
3. THE Chat_UI SHALL Reflex 표준 프로젝트 구조(wellbot/ 패키지 디렉토리, rxconfig.py)를 따른다
4. THE State_Manager SHALL Reflex의 rx.State 클래스를 상속하여 구현된다

### 요구사항 7: 시각적 테마 및 스타일링

**사용자 스토리:** 사용자로서, 깔끔하고 현대적인 디자인의 챗봇 인터페이스를 원한다. 이를 통해 쾌적한 사용 경험을 얻을 수 있다.

#### 인수 조건

1. THE Chat_UI SHALL 다크 모드 기반의 색상 테마를 기본으로 적용한다
2. THE Chat_UI SHALL 일관된 색상 팔레트와 타이포그래피를 사용한다
3. THE Input_Bar SHALL 둥근 모서리와 적절한 패딩을 가진 입력 필드를 렌더링한다
4. THE Sidebar SHALL 메인 대화 영역과 시각적으로 구분되는 배경색을 사용한다

### 요구사항 8: 로그인 및 인증

**사용자 스토리:** 사용자로서, 로그인 페이지를 통해 인증된 상태로 챗봇에 접속하고 싶다. 이를 통해 개인화된 대화 환경을 안전하게 이용할 수 있다.

#### 인수 조건

1. THE Chat_UI SHALL 인증되지 않은 사용자를 Login_Page로 리다이렉트한다
2. THE Login_Page SHALL 이메일 입력 필드, 비밀번호 입력 필드, 로그인 버튼을 포함한다
3. WHEN 사용자가 유효한 이메일과 비밀번호를 입력하고 로그인 버튼을 클릭하면, THE Auth_State SHALL MySQL DB에서 bcrypt 해싱된 비밀번호를 검증하고 JWT를 발급한 후 Chat_UI 메인 화면으로 리다이렉트한다
4. WHEN 사용자가 로그인 폼에서 Enter 키를 누르면, THE Auth_State SHALL 로그인 버튼 클릭과 동일한 인증 처리를 수행한다
5. IF 사용자가 잘못된 이메일 또는 비밀번호를 입력하면, THEN THE Login_Page SHALL 상단 토스트 알림으로 오류 메시지를 표시한다
6. WHILE 인증 요청이 처리되는 동안, THE Login_Page SHALL 로그인 버튼을 비활성화하고 로딩 상태를 표시한다
7. THE Login_Page SHALL Chat_UI와 일관된 다크 모드 테마를 적용한다
