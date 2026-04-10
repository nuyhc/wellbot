"""대화 상태 관리 - ChatState.

메시지 전송, 대화 생성/전환/삭제, Bedrock 스트리밍 응답 처리를 담당한다.
"""

import time
import uuid

from pydantic import BaseModel
import reflex as rx

from wellbot.services.bedrock_client import astream_chat
from wellbot.services.config import get_config


TITLE_MAX_LENGTH: int = 30


class ModelInfo(BaseModel):
    """프론트엔드 표시용 모델 정보."""

    name: str
    description: str
    supports_thinking: bool


class PromptInfo(BaseModel):
    """프론트엔드 표시용 프롬프트 템플릿 정보."""

    name: str
    content: str
    description: str = ""


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
    is_thinking: bool = False
    streaming_content: str = ""
    selected_model: str = ""
    thinking_enabled: bool = False
    selected_prompt: str = "default"
    show_style_panel: bool = False

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

    def _update_conversation(self, idx: int, **kwargs: object) -> None:
        """대화를 불변적으로 업데이트한다."""
        conv = self.conversations[idx]
        updated = Conversation(
            id=conv.id,
            title=kwargs.get("title", conv.title),  # type: ignore[arg-type]
            messages=kwargs.get("messages", conv.messages),  # type: ignore[arg-type]
            created_at=conv.created_at,
        )
        self.conversations = [
            updated if c.id == updated.id else c for c in self.conversations
        ]

    # ── Computed vars ──

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

    @rx.var
    def model_names(self) -> list[str]:
        """사용 가능한 모델 이름 목록."""
        try:
            return get_config().model_names
        except Exception:
            return []

    @rx.var
    def model_list(self) -> list[ModelInfo]:
        """팝오버 표시용 모델 목록."""
        try:
            cfg = get_config()
            return [
                ModelInfo(
                    name=m.name,
                    description=m.description,
                    supports_thinking=m.thinking,
                )
                for m in cfg.models
            ]
        except Exception:
            return []

    @rx.var
    def trigger_label(self) -> str:
        """모델 선택 트리거 버튼 라벨."""
        label = self.selected_model
        if self.thinking_enabled and self.model_supports_thinking:
            label += " 확장"
        return label

    @rx.var
    def has_streaming(self) -> bool:
        """스트리밍 중인 텍스트 컨텐츠가 있는지 여부."""
        return self.is_loading and bool(self.streaming_content) and not self.is_thinking

    @rx.var
    def model_supports_thinking(self) -> bool:
        """현재 선택된 모델이 thinking을 지원하는지 여부."""
        try:
            cfg = get_config()
            model = cfg.get_model(self.selected_model)
            return model.thinking if model else False
        except Exception:
            return False

    @rx.var
    def prompt_list(self) -> list[PromptInfo]:
        """사용 가능한 프롬프트 템플릿 목록."""
        try:
            cfg = get_config()
            return [
                PromptInfo(name=p.name, content=p.content, description=p.description)
                for p in cfg.prompts
            ]
        except Exception as e:
            print(f"[prompt_list] 프롬프트 로드 실패: {e}")
            return []

    @rx.var
    def current_system_prompt(self) -> str:
        """현재 선택된 시스템 프롬프트 내용."""
        try:
            cfg = get_config()
            p = cfg.get_prompt(self.selected_prompt)
            return p.content if p else cfg.system_prompt
        except Exception:
            return ""

    # ── Event handlers ──

    def on_load(self) -> None:
        """페이지 로드 시 초기화."""
        self._ensure_conversation()
        if not self.selected_model:
            try:
                self.selected_model = get_config().default_model.name
            except Exception:
                pass

    def set_model(self, name: str) -> None:
        """사용 모델을 변경한다."""
        self.selected_model = name
        self.thinking_enabled = False

    def toggle_thinking(self, checked: bool) -> None:
        """thinking 활성화/비활성화를 토글한다."""
        self.thinking_enabled = checked

    def toggle_style_panel(self) -> None:
        """스타일 패널 표시/숨김을 토글한다."""
        self.show_style_panel = not self.show_style_panel

    def select_prompt(self, name: str) -> None:
        """시스템 프롬프트 템플릿을 선택하고 패널을 닫는다."""
        self.selected_prompt = name
        self.show_style_panel = False

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
        """메시지를 전송하고 Bedrock 스트리밍 응답을 처리한다."""
        # 1. 사용자 메시지 추가 및 상태 초기화
        async with self:
            text = self.current_input.strip()
            if not text or self.is_loading:
                return

            self._ensure_conversation()
            idx = self._get_current_index()
            if idx is None:
                return

            user_msg = Message(
                role="user",
                content=text,
                timestamp=time.time(),
            )
            updated_messages = [*self.conversations[idx].messages, user_msg]

            # 첫 번째 사용자 메시지로 대화 제목 설정
            title = self.conversations[idx].title
            user_msgs = [m for m in updated_messages if m.role == "user"]
            if len(user_msgs) == 1:
                title = text[:TITLE_MAX_LENGTH]
                if len(text) > TITLE_MAX_LENGTH:
                    title += "..."

            self._update_conversation(idx, title=title, messages=updated_messages)
            self.current_input = ""
            self.is_loading = True
            self.is_thinking = False
            self.streaming_content = ""

            # API 호출용 메시지 준비
            api_messages = [
                {"role": m.role, "content": m.content}
                for m in updated_messages
            ]
            model_name = self.selected_model
            use_thinking = self.thinking_enabled
            prompt_name = self.selected_prompt

        # 2. Bedrock 스트리밍 호출
        content = ""
        try:
            cfg = get_config()
            model = cfg.get_model(model_name) or cfg.default_model
            prompt = cfg.get_prompt(prompt_name)
            system_prompt = prompt.content if prompt else cfg.system_prompt

            async for event_type, chunk in astream_chat(
                api_messages, model, system_prompt,
                thinking_enabled=use_thinking,
            ):
                if event_type == "thinking":
                    async with self:
                        self.is_thinking = True
                elif event_type == "text":
                    content += chunk
                    async with self:
                        self.is_thinking = False
                        self.streaming_content = content

        except Exception as e:
            content = f"오류가 발생했습니다: {e}"

        # 3. 최종 AI 메시지를 대화에 저장
        async with self:
            idx = self._get_current_index()
            if idx is not None and content:
                ai_msg = Message(
                    role="assistant",
                    content=content,
                    timestamp=time.time(),
                )
                updated = [*self.conversations[idx].messages, ai_msg]
                self._update_conversation(idx, messages=updated)

            self.is_loading = False
            self.is_thinking = False
            self.streaming_content = ""
