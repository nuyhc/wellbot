"""대화 상태 관리 - ChatState.

메시지 전송, 대화 생성/전환/삭제, Bedrock 스트리밍 응답 처리를 담당한다.
DB 연동으로 대화 이력을 영속화한다.
"""

import time
import uuid

from pydantic import BaseModel
import reflex as rx

from wellbot.services.bedrock_client import astream_chat
from wellbot.services import chat_service
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
    model_name: str = ""
    seq: int = 0


class Conversation(BaseModel):
    """대화 세션 모델."""

    id: str
    title: str
    messages: list[Message]
    created_at: float
    model_name: str = ""
    is_loaded: bool = False      # 메시지가 DB에서 로드되었는지
    is_persisted: bool = False   # DB에 저장된 대화인지


def _new_conversation() -> Conversation:
    """빈 대화를 생성한다."""
    now = time.time()
    return Conversation(
        id=str(uuid.uuid4()),
        title="새 대화",
        messages=[],
        created_at=now,
        is_loaded=True,
        is_persisted=False,
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

    # 인증된 사용자 (on_load에서 캐시)
    _emp_no: str = ""

    def _ensure_conversation(self) -> None:
        """대화가 없으면 새로 생성."""
        if not self.conversations:
            conv = _new_conversation()
            self.conversations = [conv]
            self.current_conversation_id = conv.id

    def _get_current_index(self) -> int | None:
        """현재 대화의 인덱스 반환."""
        for i, conv in enumerate(self.conversations):
            if conv.id == self.current_conversation_id:
                return i
        return None

    def _update_conversation(self, idx: int, **kwargs: object) -> None:
        """대화 업데이트."""
        conv = self.conversations[idx]
        updated = Conversation(
            id=conv.id,
            title=kwargs.get("title", conv.title),  # type: ignore[arg-type]
            messages=kwargs.get("messages", conv.messages),  # type: ignore[arg-type]
            created_at=conv.created_at,
            model_name=kwargs.get("model_name", conv.model_name),  # type: ignore[arg-type]
            is_loaded=kwargs.get("is_loaded", conv.is_loaded),  # type: ignore[arg-type]
            is_persisted=kwargs.get("is_persisted", conv.is_persisted),  # type: ignore[arg-type]
        )
        self.conversations = [
            updated if c.id == updated.id else c for c in self.conversations
        ]

    def _load_messages_for(self, idx: int) -> None:
        """DB에서 대화의 메시지를 로드."""
        conv = self.conversations[idx]
        if conv.is_loaded:
            return
        msgs = chat_service.get_conversation_messages(conv.id, self._emp_no)
        loaded = [
            Message(
                role=m["role"],
                content=m["content"],
                timestamp=m["timestamp"],
                model_name=m.get("model_name", ""),
                seq=m.get("seq", 0),
            )
            for m in msgs
        ]
        self._update_conversation(idx, messages=loaded, is_loaded=True)

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
        """전송 가능 여부 (대화 선택됨, 입력이 비어있지 않고 로딩 중이 아님)."""
        if self._get_current_index() is None:
            return False
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

    async def on_load(self) -> None:
        """페이지 로드 시 초기화: DB에서 대화 목록 로드."""
        # AuthState에서 emp_no 획득
        from wellbot.state.auth_state import AuthState
        auth = await self.get_state(AuthState)
        self._emp_no = auth.current_emp_no

        # 모델/프롬프트 초기화
        try:
            cfg = get_config()
            if not self.selected_model:
                self.selected_model = cfg.default_model.name
            if self.selected_prompt == "default":
                for p in cfg.prompts:
                    if p.content == cfg.system_prompt:
                        self.selected_prompt = p.name
                        break
        except Exception:
            pass

        # DB에서 대화 목록 로드
        if self._emp_no:
            convs = chat_service.list_conversations(self._emp_no)
            db_conversations = [
                Conversation(
                    id=c["id"],
                    title=c["title"],
                    messages=[],
                    created_at=c["created_at"],
                    model_name=c.get("model_name", ""),
                    is_loaded=False,
                    is_persisted=True,
                )
                for c in convs
            ]
            if db_conversations:
                self.conversations = db_conversations
                self.current_conversation_id = db_conversations[0].id
                # 첫 번째 대화의 메시지 로드
                self._load_messages_for(0)
            else:
                self._ensure_conversation()
        else:
            self._ensure_conversation()

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
        prev_prompt = self.selected_prompt
        self.selected_prompt = name
        self.show_style_panel = False

        # 프롬프트가 변경되고, 대화가 DB에 저장된 상태면 system 메시지 기록
        if name != prev_prompt and self._emp_no:
            idx = self._get_current_index()
            if idx is not None and self.conversations[idx].is_persisted:
                try:
                    cfg = get_config()
                    prompt = cfg.get_prompt(name)
                    sys_content = prompt.content if prompt else ""
                    if sys_content:
                        conv_id = self.conversations[idx].id
                        seq = chat_service.get_next_seq(conv_id)
                        chat_service.save_message(
                            smry_id=conv_id, seq=seq,
                            role="system", content=sys_content,
                            emp_no=self._emp_no, model_name=name,
                        )
                except Exception:
                    pass

    def create_new_conversation(self) -> None:
        """새 대화를 생성한다. 현재 대화가 비어있으면 무시."""
        idx = self._get_current_index()
        if idx is not None and not self.conversations[idx].messages:
            return
        conv = _new_conversation()
        self.conversations = [conv, *self.conversations]
        self.current_conversation_id = conv.id
        self.current_input = ""

    def switch_conversation(self, conv_id: str) -> None:
        """대화를 전환한다. 미로드 시 DB에서 메시지 로드."""
        self.current_conversation_id = conv_id
        self.current_input = ""
        idx = self._get_current_index()
        if idx is not None:
            self._load_messages_for(idx)
        return rx.call_script(  # type: ignore[return-value]
            "if (window.__resetAutoScroll) { window.__resetAutoScroll(); }"
        )

    def delete_conversation(self, conv_id: str) -> None:
        """대화를 삭제한다. DB에서도 삭제."""
        conv = next((c for c in self.conversations if c.id == conv_id), None)
        if conv and conv.is_persisted:
            try:
                chat_service.delete_conversation(conv_id, self._emp_no)
            except Exception:
                pass
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
            is_first_msg = not any(m.role == "user" for m in self.conversations[idx].messages)
            if is_first_msg:
                title = text[:TITLE_MAX_LENGTH]
                if len(text) > TITLE_MAX_LENGTH:
                    title += "..."

            self._update_conversation(idx, title=title, messages=updated_messages)
            self.current_input = ""
            self.is_loading = True
            self.is_thinking = False
            self.streaming_content = ""

            # DB 저장용 로컬 변수
            conv_id = self.conversations[idx].id
            is_persisted = self.conversations[idx].is_persisted
            emp_no = self._emp_no
            model_name = self.selected_model
            use_thinking = self.thinking_enabled
            prompt_name = self.selected_prompt

            # API 호출용 메시지 준비
            api_messages = [
                {"role": m.role, "content": m.content}
                for m in updated_messages
            ]

        # DB 저장: 대화 + 시스템 프롬프트 + 사용자 메시지 (State 락 밖)
        if emp_no:
            if not is_persisted:
                chat_service.save_conversation(emp_no, conv_id, title, model_name)
                # 시스템 프롬프트를 첫 번째 메시지로 저장
                try:
                    cfg = get_config()
                    prompt = cfg.get_prompt(prompt_name)
                    sys_content = prompt.content if prompt else cfg.system_prompt
                    sys_seq = chat_service.get_next_seq(conv_id)
                    chat_service.save_message(
                        smry_id=conv_id, seq=sys_seq,
                        role="system", content=sys_content,
                        emp_no=emp_no, model_name=prompt_name,
                    )
                except Exception:
                    pass
            elif is_first_msg:
                chat_service.update_conversation_title(conv_id, title, emp_no)
            user_seq = chat_service.get_next_seq(conv_id)
            chat_service.save_message(
                smry_id=conv_id, seq=user_seq,
                role="user", content=text,
                emp_no=emp_no, model_name=model_name,
                provider=prompt_name,
            )

        # is_persisted 업데이트
        async with self:
            idx = self._get_current_index()
            if idx is not None and not self.conversations[idx].is_persisted:
                self._update_conversation(idx, is_persisted=True)

        # 2. Bedrock 스트리밍 호출
        content = ""
        start_time = time.time()
        input_tokens = 0
        output_tokens = 0
        provider = ""
        try:
            cfg = get_config()
            model = cfg.get_model(model_name) or cfg.default_model
            provider = model.provider
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
                elif event_type == "usage":
                    input_tokens = chunk.get("inputTokens", 0)
                    output_tokens = chunk.get("outputTokens", 0)

        except Exception as e:
            content = "오류가 발생했습니다."

        finally:
            # 3. 최종 AI 메시지를 대화에 저장 + 상태 복구
            async with self:
                idx = self._get_current_index()
                if idx is not None and content:
                    ai_msg = Message(
                        role="assistant",
                        content=content,
                        timestamp=time.time(),
                        model_name=model_name,
                    )
                    updated = [*self.conversations[idx].messages, ai_msg]
                    self._update_conversation(idx, messages=updated)

                self.is_loading = False
                self.is_thinking = False
                self.streaming_content = ""

        # DB 저장: AI 응답 메시지 (State 락 밖)
        if emp_no and content:
            elapsed = round(time.time() - start_time, 2)
            ai_seq = chat_service.get_next_seq(conv_id)
            chat_service.save_message(
                smry_id=conv_id, seq=ai_seq,
                role="assistant", content=content,
                emp_no=emp_no, model_name=model_name,
                provider=provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                reply_time=elapsed,
            )
