"""대화 상태 관리 - ChatState.

메시지 전송, 대화 생성/전환/삭제, 스텁 응답 처리를 담당한다.
"""

import asyncio
import random
import time
import uuid

from pydantic import BaseModel
import reflex as rx


STUB_RESPONSES: list[str] = [
    "안녕하세요! 무엇을 도와드릴까요?",
    "흥미로운 질문이네요. 좀 더 자세히 말씀해 주시겠어요?",
    "네, 이해했습니다. 다음과 같이 답변드릴 수 있습니다:\n\n"
    "1. **첫 번째 포인트**: 데이터를 분석해보면 흥미로운 패턴이 보입니다.\n"
    "2. **두 번째 포인트**: 추가적인 정보가 필요할 수 있습니다.\n"
    "3. **세 번째 포인트**: 결론적으로 더 깊이 살펴볼 가치가 있습니다.",
    "좋은 질문입니다! 아래 코드를 참고해 주세요:\n\n"
    "```python\ndef hello():\n    print('Hello, World!')\n```\n\n"
    "이 코드는 간단한 예시입니다.",
    "해당 내용에 대해 다음과 같이 정리해 드리겠습니다:\n\n"
    "- 기본 개념을 먼저 이해하는 것이 중요합니다\n"
    "- 실습을 통해 익숙해지는 것을 권장합니다\n"
    "- 궁금한 점이 있으면 언제든 물어보세요!",
    "그 부분에 대해서는 조금 더 생각해볼 필요가 있습니다. "
    "다른 관점에서 접근해 보시는 건 어떨까요?",
]

TITLE_MAX_LENGTH: int = 30


class Message(BaseModel):
    """개별 메시지 모델."""

    role: str  # "user" | "assistant"
    content: str
    timestamp: float


class Conversation(BaseModel):
    """대화 세션 모델."""

    id: str
    title: str
    messages: list[Message]
    created_at: float


def _new_conversation() -> Conversation:
    """빈 대화를 생성한다."""
    now = time.time()
    return Conversation(
        id=str(uuid.uuid4()),
        title="새 대화",
        messages=[],
        created_at=now,
    )


class ChatState(rx.State):
    """채팅 관련 상태를 관리하는 State 클래스."""

    conversations: list[Conversation] = []
    current_conversation_id: str = ""
    current_input: str = ""
    is_loading: bool = False

    def _ensure_conversation(self) -> None:
        """대화가 없으면 새로 생성한다."""
        if not self.conversations:
            conv = _new_conversation()
            self.conversations = [conv]
            self.current_conversation_id = conv.id

    def _get_current_index(self) -> int | None:
        """현재 대화의 인덱스를 반환한다."""
        for i, conv in enumerate(self.conversations):
            if conv.id == self.current_conversation_id:
                return i
        return None

    @rx.var
    def current_messages(self) -> list[Message]:
        """현재 대화의 메시지 목록."""
        idx = self._get_current_index()
        if idx is None:
            return []
        return self.conversations[idx].messages

    @rx.var
    def has_messages(self) -> bool:
        """현재 대화에 메시지가 있는지 여부."""
        return len(self.current_messages) > 0

    @rx.var
    def can_send(self) -> bool:
        """전송 가능 여부 (입력이 비어있지 않고 로딩 중이 아님)."""
        return self.current_input.strip() != "" and not self.is_loading

    @rx.var
    def sorted_conversations(self) -> list[Conversation]:
        """시간 역순으로 정렬된 대화 목록."""
        return sorted(
            self.conversations,
            key=lambda c: c.created_at,
            reverse=True,
        )

    def on_load(self) -> None:
        """페이지 로드 시 초기화."""
        self._ensure_conversation()

    def create_new_conversation(self) -> None:
        """새 대화를 생성한다."""
        conv = _new_conversation()
        self.conversations = [conv, *self.conversations]
        self.current_conversation_id = conv.id
        self.current_input = ""

    def switch_conversation(self, conv_id: str) -> None:
        """대화를 전환한다."""
        self.current_conversation_id = conv_id
        self.current_input = ""

    def delete_conversation(self, conv_id: str) -> None:
        """대화를 삭제한다."""
        self.conversations = [c for c in self.conversations if c.id != conv_id]
        if conv_id == self.current_conversation_id:
            if self.conversations:
                self.current_conversation_id = self.conversations[0].id
            else:
                self._ensure_conversation()

    def set_input(self, value: str) -> None:
        """입력 필드 값을 설정한다."""
        self.current_input = value

    @rx.event(background=True)
    async def send_message(self, form_data: dict | None = None) -> None:
        """메시지를 전송하고 스텁 응답을 생성한다."""
        async with self:
            text = self.current_input.strip()
            if not text or self.is_loading:
                return

            self._ensure_conversation()
            idx = self._get_current_index()
            if idx is None:
                return

            # 사용자 메시지 추가
            user_msg = Message(
                role="user",
                content=text,
                timestamp=time.time(),
            )
            updated_messages = [*self.conversations[idx].messages, user_msg]

            # 첫 번째 사용자 메시지로 대화 제목 설정
            title = self.conversations[idx].title
            user_messages = [m for m in updated_messages if m.role == "user"]
            if len(user_messages) == 1:
                title = text[:TITLE_MAX_LENGTH]
                if len(text) > TITLE_MAX_LENGTH:
                    title += "..."

            updated_conv = Conversation(
                id=self.conversations[idx].id,
                title=title,
                messages=updated_messages,
                created_at=self.conversations[idx].created_at,
            )
            self.conversations = [
                updated_conv if c.id == updated_conv.id else c
                for c in self.conversations
            ]
            self.current_input = ""
            self.is_loading = True

        # 스텁 응답 지연 (0.5~3초)
        delay = random.uniform(0.5, 3.0)
        await asyncio.sleep(delay)

        async with self:
            idx = self._get_current_index()
            if idx is None:
                self.is_loading = False
                return

            ai_msg = Message(
                role="ai",
                content=random.choice(STUB_RESPONSES),
                timestamp=time.time(),
            )
            updated_messages = [*self.conversations[idx].messages, ai_msg]
            updated_conv = Conversation(
                id=self.conversations[idx].id,
                title=self.conversations[idx].title,
                messages=updated_messages,
                created_at=self.conversations[idx].created_at,
            )
            self.conversations = [
                updated_conv if c.id == updated_conv.id else c
                for c in self.conversations
            ]
            self.is_loading = False
