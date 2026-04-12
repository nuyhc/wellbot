"""Wellbot 설정 상수.

설정값을 중앙 관리
"""

# ── 인증/세션 ──
TOKEN_EXPIRE_HOURS: int = 3
TOKEN_EXPIRE_SECONDS: int = TOKEN_EXPIRE_HOURS * 3600  # 쿠키 max_age용
LOCK_THRESHOLD: int = 5            # 로그인 실패 잠금 횟수
LOCK_DURATION_MINUTES: int = 30    # 계정 잠금 시간(분)
PASSWORD_MIN_LENGTH: int = 8       # 비밀번호 최소 길이

# ── 채팅 ──
CONVERSATION_LIMIT: int = 30       # 사이드바 대화 목록 최대 수
TITLE_MAX_LENGTH: int = 30         # 임시 제목 최대 글자 수
DEFAULT_CONVERSATION_TITLE: str = "새 대화"

# ── 제목 생성 (경량 모델) ──
TITLE_MODEL_ID: str = "apac.amazon.nova-lite-v1:0"
TITLE_MAX_TOKENS: int = 30
TITLE_TEMPERATURE: float = 0.3
TITLE_SYSTEM_PROMPT: str = (
    "대화의 첫 질문과 응답을 보고, 이 대화를 대표하는 짧은 제목을 한국어로 만들어주세요. "
    "15자 이내로, 제목만 출력하세요. 따옴표나 부가 설명 없이 제목 텍스트만 응답하세요."
)

# ── UI ──
SCROLL_THRESHOLD: int = 100        # 자동 스크롤 유지 판정(px)
BTN_THRESHOLD: int = 30            # 스크롤 버튼 표시 판정(px)
