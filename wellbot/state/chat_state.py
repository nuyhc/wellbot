"""대화 상태 관리 - ChatState.

메시지 전송, 대화 생성/전환/삭제, Bedrock 스트리밍 응답 처리를 담당.
DB 연동으로 대화 이력을 영속화(persistence) 보장.
"""

import asyncio
import random
import time
import uuid

from pydantic import BaseModel
import reflex as rx

from wellbot.constants import (
    DEFAULT_CONVERSATION_TITLE,
    FILE_MAX_PER_MESSAGE,
    FILE_MAX_SIZE_MB,
    FILE_PARSER_MODE,
    LOCAL_SUPPORTED_EXTS,
    TITLE_MAX_LENGTH,
    TOOL_USE_MAX_ITERATIONS,
    UPSTAGE_SUPPORTED_EXTS,
)
from wellbot.services.bedrock_client import (
    astream_chat,
    astream_chat_with_tools,
    generate_title,
    image_format,
)
from wellbot.services import attachment_service, chat_service, file_parser, response_filter, tool_executor
from wellbot.services.config import get_config, get_greetings


class AgentModeInfo(BaseModel):
    """프론트엔드 표시용 에이전트 모드 정보."""

    id: str
    name: str
    description: str = ""
    icon: str = "message-circle"


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


class AttachmentInfo(BaseModel):
    """프론트엔드 표시용 첨부파일 정보."""

    file_no: int
    name: str
    mime: str = ""
    size_bytes: int = 0
    token_count: int = 0
    status: str = "processing"  # "processing" | "ready" | "failed"


class Message(BaseModel):
    """개별 메시지 모델."""

    role: str  # "user" | "assistant"
    content: str
    timestamp: float
    model_name: str = ""
    seq: int = 0
    attachments: list[AttachmentInfo] = []


class Conversation(BaseModel):
    """대화 세션 모델."""

    id: str
    title: str
    messages: list[Message]
    created_at: float
    model_name: str = ""
    is_loaded: bool = False      # 메시지가 DB에서 로드되었는지
    is_persisted: bool = False   # DB에 저장된 대화인지


_MIME_LABELS: dict[str, str] = {
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PowerPoint",
    "application/x-hwp": "한글",
    "application/x-hwpx": "한글",
    "text/plain": "텍스트",
    "text/markdown": "Markdown",
    "image/png": "PNG 이미지",
    "image/jpeg": "JPEG 이미지",
    "image/webp": "WebP 이미지",
    "image/gif": "GIF 이미지",
}


def _mime_to_label(mime: str) -> str:
    """MIME 타입을 한국어 라벨로 변환."""
    return _MIME_LABELS.get(mime, mime or "파일")


def _new_conversation() -> Conversation:
    """빈 대화를 생성한다."""
    now = time.time()
    return Conversation(
        id=str(uuid.uuid4()),
        title=DEFAULT_CONVERSATION_TITLE,
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
    greeting_text: str = ""

    # ── 에이전트 모드 ──
    selected_agent_mode: str = "chat"

    # ── 첨부파일 ──
    pending_attachments: list[AttachmentInfo] = []
    attachment_error: str = ""

    # ── 생성 중지 ──
    _cancel_requested: bool = False

    # 인증된 사용자 (on_load에서 캐시)
    _emp_no: str = ""

    def _refresh_greeting(self) -> None:
        """환영 메시지를 랜덤으로 갱신."""
        self.greeting_text = random.choice(get_greetings())

    def _ensure_conversation(self) -> None:
        """대화가 없으면 새로 생성."""
        if not self.conversations:
            conv = _new_conversation()
            self.conversations = [conv]
            self.current_conversation_id = conv.id

    def _get_current_index(self) -> int | None:
        """현재 대화의 인덱스 반환. 못 찾으면 자동 복구 시도."""
        for i, conv in enumerate(self.conversations):
            if conv.id == self.current_conversation_id:
                return i
        # 자동 복구: current_id가 conversations에 없는 경우
        if self.conversations:
            self.current_conversation_id = self.conversations[0].id
            return 0
        self._ensure_conversation()
        return 0 if self.conversations else None

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
                attachments=[
                    AttachmentInfo(**a) for a in (m.get("attachments") or [])
                ],
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
    def current_title(self) -> str:
        """현재 대화의 제목."""
        idx = self._get_current_index()
        if idx is None:
            return ""
        return self.conversations[idx].title

    @rx.var
    def agent_mode_list(self) -> list[AgentModeInfo]:
        """사용 가능한 에이전트 모드 목록."""
        try:
            cfg = get_config()
            return [
                AgentModeInfo(
                    id=a.id, name=a.name,
                    description=a.description, icon=a.icon,
                )
                for a in cfg.agent_modes
            ]
        except Exception:
            return []

    @rx.var
    def current_agent_mode_name(self) -> str:
        """현재 선택된 에이전트 모드 이름."""
        try:
            cfg = get_config()
            mode = cfg.get_agent_mode(self.selected_agent_mode)
            return mode.name if mode else "기본 대화"
        except Exception:
            return "기본 대화"

    @rx.var
    def current_agent_mode_icon(self) -> str:
        """현재 선택된 에이전트 모드 아이콘."""
        try:
            cfg = get_config()
            mode = cfg.get_agent_mode(self.selected_agent_mode)
            return mode.icon if mode else "message-circle"
        except Exception:
            return "message-circle"

    @rx.var
    def has_processing_attachments(self) -> bool:
        """처리 중인 첨부파일이 있는지 여부."""
        return any(a.status == "processing" for a in self.pending_attachments)

    @rx.var
    def can_send(self) -> bool:
        """전송 가능 여부.

        처리 중인 첨부파일이 있으면 전송 차단.
        """
        if self._get_current_index() is None:
            return False
        if self.is_loading:
            return False
        if self.has_processing_attachments:
            return False
        return self.current_input.strip() != ""

    @rx.var
    def sorted_conversations(self) -> list[Conversation]:
        """시간 역순으로 정렬된 대화 목록.

        빈 미저장 대화는 숨기되, 현재 활성 대화는 항상 표시.
        """
        current_id = self.current_conversation_id
        visible = [
            c for c in self.conversations
            if c.is_persisted or c.messages or c.id == current_id
        ]
        return sorted(visible, key=lambda c: c.created_at, reverse=True)

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

    def set_agent_mode(self, mode_id: str) -> None:
        """에이전트 모드를 변경한다."""
        self.selected_agent_mode = mode_id

    def stop_generation(self) -> None:
        """사용자가 생성 중지를 요청한다."""
        if not self.is_loading:
            return
        self._cancel_requested = True

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

        # 환영 메시지 초기화
        self._refresh_greeting()

        # 이미 DB에서 대화를 로드한 상태면 재조회하지 않음
        has_db_conversations = any(c.is_persisted for c in self.conversations)
        if has_db_conversations:
            return

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
                # 기존 빈 새 대화가 있으면 재사용, 없으면 새로 생성
                existing_new = next(
                    (c for c in self.conversations if not c.is_persisted and not c.messages),
                    None,
                )
                new_conv = existing_new or _new_conversation()
                self.conversations = [new_conv, *db_conversations]
                self.current_conversation_id = new_conv.id
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
            self._refresh_greeting()
            return
        conv = _new_conversation()
        self.conversations = [conv, *self.conversations]
        self.current_conversation_id = conv.id
        self.current_input = ""
        self._refresh_greeting()

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
            # 빈 새 대화가 이미 있으면 그쪽으로, 없으면 새로 생성
            empty = next(
                (c for c in self.conversations if not c.messages and not c.is_persisted),
                None,
            )
            if empty:
                self.current_conversation_id = empty.id
            else:
                new_conv = _new_conversation()
                self.conversations = [new_conv, *self.conversations]
                self.current_conversation_id = new_conv.id

    def set_input(self, value: str) -> None:
        """입력 필드 값을 설정한다."""
        self.current_input = value

    # ── 첨부파일 ──

    @rx.var
    def accepted_file_extensions(self) -> str:
        """현재 파서 모드 + 현재 선택된 모델의 vision 지원에 따라 허용 확장자 CSV."""
        mode = (FILE_PARSER_MODE or "local").lower()
        if mode == "local":
            allowed = set(LOCAL_SUPPORTED_EXTS | file_parser.IMAGE_EXTS)
        elif mode == "upstage":
            allowed = set(UPSTAGE_SUPPORTED_EXTS)
        else:
            allowed = set(LOCAL_SUPPORTED_EXTS | UPSTAGE_SUPPORTED_EXTS)

        # 현재 모델이 vision 미지원이면 이미지 확장자 제외
        if not self.model_supports_vision:
            allowed -= set(file_parser.IMAGE_EXTS)

        return ",".join(sorted(allowed))

    @rx.var
    def model_supports_vision(self) -> bool:
        """현재 모델이 이미지 입력을 지원하는지."""
        try:
            cfg = get_config()
            model = cfg.get_model(self.selected_model)
            return bool(model and getattr(model, "supports_vision", False))
        except Exception:
            return False

    @rx.var
    def has_pending_attachments(self) -> bool:
        """첨부 칩 영역 표시 여부."""
        return len(self.pending_attachments) > 0

    def _ensure_conversation_persisted(self) -> str:
        """파일 업로드 전에 대화를 DB 에 persist 하고 ID 반환."""
        self._ensure_conversation()
        idx = self._get_current_index()
        if idx is None:
            return ""
        conv = self.conversations[idx]
        if not conv.is_persisted and self._emp_no:
            try:
                chat_service.save_conversation(
                    self._emp_no,
                    conv.id,
                    conv.title or DEFAULT_CONVERSATION_TITLE,
                    self.selected_model,
                )
                self._update_conversation(idx, is_persisted=True)
            except Exception:
                pass
        return conv.id

    def set_attachment_error(self, message: str) -> None:
        """첨부 관련 에러 메시지 설정."""
        self.attachment_error = message

    def remove_pending_attachment(self, file_no: int) -> None:
        """pending 목록에서 제거 (UI 삭제 버튼)."""
        if self._emp_no:
            try:
                attachment_service.delete_attachment(file_no, self._emp_no)
            except Exception:
                pass
        self.pending_attachments = [
            a for a in self.pending_attachments if a.file_no != file_no
        ]

    def download_attachment(self, file_no: int) -> rx.event.EventSpec | None:
        """첨부파일 presigned URL 을 열어 다운로드한다."""
        if not self._emp_no:
            return None
        if not attachment_service.verify_ownership(file_no, self._emp_no):
            return None
        url = attachment_service.get_download_url(file_no)
        if not url:
            return None
        # 숨겨진 <a> 태그로 새 창 없이 다운로드 트리거
        safe_url = url.replace("'", "\\'")
        return rx.call_script(
            f"(function(){{ var a=document.createElement('a'); a.href='{safe_url}'; a.download=''; document.body.appendChild(a); a.click(); a.remove(); }})()"
        )

    def _sync_attachments_from_db(self) -> None:
        """현재 대화의 첨부파일 목록을 DB 에서 읽어 pending 갱신."""
        if not self._emp_no or not self.current_conversation_id:
            return
        try:
            rows = attachment_service.get_conversation_attachments(
                self.current_conversation_id
            )
        except Exception:
            return
        # 메시지에 이미 할당된 file_no 는 pending 에서 제외 (대화 저장 후 이동)
        assigned: set[int] = set()
        idx = self._get_current_index()
        if idx is not None:
            for m in self.conversations[idx].messages:
                for a in (m.attachments or []):
                    assigned.add(a.file_no)

        self.pending_attachments = [
            AttachmentInfo(
                file_no=r.file_no,
                name=r.file_name,
                mime=r.mime,
                token_count=r.token_count or 0,
                status="ready" if r.token_count is not None else "processing",
            )
            for r in rows
            if r.file_no not in assigned
        ]

    @rx.event(background=True)
    async def poll_attachments(self) -> None:
        """업로드 트리거 후 일정 시간 동안 DB 를 폴링해 UI 갱신."""
        deadline = time.time() + 30.0  # 최대 30초
        interval = 1.0
        while time.time() < deadline:
            async with self:
                self._sync_attachments_from_db()
            await asyncio.sleep(interval)
            interval = min(2.0, interval + 0.5)

    def trigger_upload(self) -> rx.event.EventSpec | None:
        """파일 선택 다이얼로그를 열고 업로드를 트리거한다.

        구조:
            1. 대화가 미 persist 상태라면 DB 저장
            2. JS 가 파일 선택 + fetch POST /api/upload 실행
            3. `poll_attachments` 백그라운드 이벤트가 DB 를 폴링해 UI 갱신
        """
        self.attachment_error = ""
        conv_id = self._ensure_conversation_persisted()
        if not conv_id:
            self.attachment_error = "대화를 먼저 생성할 수 없습니다."
            return None

        if len(self.pending_attachments) >= FILE_MAX_PER_MESSAGE:
            self.attachment_error = (
                f"메시지당 최대 {FILE_MAX_PER_MESSAGE}개까지 첨부 가능합니다."
            )
            return None

        accept = self.accepted_file_extensions
        max_mb = FILE_MAX_SIZE_MB
        max_per_msg = FILE_MAX_PER_MESSAGE
        current_count = len(self.pending_attachments)

        # JS: 파일 선택 → fetch POST /api/upload (백엔드 직접)
        # Nginx/ALB 프록시 환경: 상대 경로 (/api/upload) 사용
        # 로컬 개발 (포트 분리) 환경: env.json PING origin 과 window.location.origin 비교
        # 완료 알림은 Python 측 polling 으로 DB 에서 감지
        script = f"""
(async function() {{
  try {{
    // 백엔드 URL 결정
    // 기본: 상대 경로 (Nginx/ALB 리버스 프록시 환경)
    // 로컬 개발 (localhost 포트 분리) 환경에서만 origin 을 붙인다
    let backendBase = '';
    try {{
      const envResp = await fetch('/env.json');
      const env = await envResp.json();
      const pingUrl = env.PING || '';
      if (pingUrl) {{
        const u = new URL(pingUrl);
        const loc = window.location;
        // 둘 다 localhost 이고 포트만 다른 경우 = 로컬 개발 환경
        const isLocalDev = (
          (loc.hostname === 'localhost' || loc.hostname === '127.0.0.1') &&
          (u.hostname === 'localhost' || u.hostname === '127.0.0.1') &&
          u.port !== loc.port
        );
        if (isLocalDev) {{
          // 쿠키가 전달되도록 hostname 을 현재 페이지와 동일하게 맞춘다
          backendBase = loc.protocol + '//' + loc.hostname + ':' + u.port;
        }}
        // 그 외 (ALB/Nginx 프록시 등): 상대 경로 사용 (backendBase = '')
      }}
    }} catch(e) {{}}

    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.accept = '{accept}';
    input.style.display = 'none';
    document.body.appendChild(input);

    const files = await new Promise((resolve) => {{
      input.onchange = () => resolve(Array.from(input.files || []));
      input.addEventListener('cancel', () => resolve([]));
      input.click();
    }});
    document.body.removeChild(input);
    if (!files.length) return;

    const maxPerMsg = {max_per_msg};
    const current = {current_count};
    if (files.length + current > maxPerMsg) {{
      alert(`메시지당 최대 ${{maxPerMsg}}개까지 첨부 가능합니다.`);
      return;
    }}

    const maxBytes = {max_mb} * 1024 * 1024;
    const errors = [];
    for (const file of files) {{
      if (file.size > maxBytes) {{
        errors.push(`'${{file.name}}' 파일이 {max_mb}MB 를 초과합니다.`);
        continue;
      }}
      const form = new FormData();
      form.append('file', file);
      form.append('conversation_id', '{conv_id}');
      try {{
        const resp = await fetch(backendBase + '/api/upload', {{
          method: 'POST',
          body: form,
          credentials: 'include',
        }});
        if (!resp.ok) {{
          const data = await resp.json().catch(() => ({{}}));
          errors.push(`'${{file.name}}': ${{data.detail || resp.status}}`);
        }}
      }} catch (err) {{
        errors.push(`'${{file.name}}': ${{err && err.message ? err.message : err}}`);
      }}
    }}
    if (errors.length) alert(errors.join('\\n'));
  }} catch (err) {{
    console.error('[wellbot upload] ', err);
  }}
}})();
"""
        # JS 실행 + Python 측 polling 을 함께 반환
        return [
            rx.call_script(script),
            ChatState.poll_attachments,
        ]

    def _augment_system_with_attachments(
        self,
        base_prompt: str,
        conv_id: str,
    ) -> str:
        """system prompt 에 현재 대화의 첨부파일 메타 목록을 append 한다.

        요약은 생성하지 않고 파일명/타입/크기/토큰 수만 주입 → 매 턴 ~100 토큰 (추정).
        LLM 이 내용을 알아야 하면 search_attachment tool 을 호출하도록 유도 필요.
        """
        if not conv_id:
            return base_prompt
        try:
            atts = attachment_service.get_conversation_attachments(conv_id)
        except Exception:
            return base_prompt

        if not atts:
            return base_prompt

        lines: list[str] = [
            "",
            "## 이 대화에 첨부된 파일",
            (
                "아래 파일들이 대화에 첨부되어 있습니다. "
                "사용자의 질문이 첨부 파일과 조금이라도 관련될 수 있다면, "
                "반드시 `search_attachment` 도구를 먼저 호출하여 실제 내용을 확인한 뒤 답변하세요. "
                "파일 내용을 추측하거나 일반 지식으로 대체하지 마세요. "
                "도구 호출 없이 파일 내용에 대해 답변하는 것은 금지됩니다."
            ),
            "",
        ]
        for i, a in enumerate(atts, start=1):
            mime = a.mime or ""
            type_label = _mime_to_label(mime)
            tokens = a.token_count
            token_str = f"{tokens:,} 토큰" if tokens is not None and tokens > 0 else "처리 중"
            lines.append(f"{i}. {a.file_name} ({type_label}, {token_str})")
        return f"{base_prompt}\n\n" + "\n".join(lines)

    def _collect_image_blocks(
        self,
        attachments: list[AttachmentInfo],
        model,
    ) -> list[dict]:
        """첨부 목록에서 이미지만 골라 Bedrock Converse image block 으로 변환."""
        if not attachments:
            return []

        supports_vision = getattr(model, "supports_vision", False)
        blocks: list[dict] = []

        for a in attachments:
            fmt = image_format(a.name)
            if not fmt:
                continue  # 이미지 아님

            if not supports_vision:
                # vision 미지원 모델 - UI 에서 사용자에게 이미 알렸다고 가정, 스킵
                continue

            try:
                data = attachment_service.download_original_bytes(a.file_no)
            except Exception:
                data = None
            if not data:
                continue
            blocks.append({"format": fmt, "bytes": data})

        return blocks

    @rx.event(background=True)
    async def send_message(self, form_data: dict | None = None) -> None:
        """메시지를 전송하고 Bedrock 스트리밍 응답을 처리한다."""
        # 1. 사용자 메시지 추가 및 상태 초기화
        async with self:
            text = self.current_input.strip()
            if not text or self.is_loading:
                return

            idx = self._get_current_index()
            if idx is None:
                return

            # 이번 turn 에 첨부될 파일 (pending → message 로 이동)
            turn_attachments = list(self.pending_attachments)

            user_msg = Message(
                role="user",
                content=text,
                timestamp=time.time(),
                attachments=turn_attachments,
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
            self.pending_attachments = []  # 메시지에 이동했으므로 초기화
            self.attachment_error = ""
            self.is_loading = True
            self.is_thinking = False
            self.streaming_content = ""
            self._cancel_requested = False

            # DB 저장용 로컬 변수
            conv_id = self.conversations[idx].id
            is_persisted = self.conversations[idx].is_persisted
            emp_no = self._emp_no
            model_name = self.selected_model
            use_thinking = self.thinking_enabled
            prompt_name = self.selected_prompt

            # API 호출용 메시지 준비 (기존 대화의 텍스트만 - 이미지 중복 방지)
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
            base_system = prompt.content if prompt else cfg.system_prompt

            # 대화에 붙은 전체 첨부파일 메타를 system prompt 에 append
            system_prompt = self._augment_system_with_attachments(base_system, conv_id)

            # 이번 turn 의 이미지 첨부를 content block 으로 변환 (마지막 user 메시지에만)
            image_blocks = self._collect_image_blocks(turn_attachments, model)
            if image_blocks and api_messages:
                api_messages[-1] = {**api_messages[-1], "image_blocks": image_blocks}

            # 대화에 첨부파일이 있으면 tool use (search_attachment) 활성화
            has_attachments = False
            try:
                has_attachments = bool(
                    attachment_service.get_conversation_attachments(conv_id)
                )
            except Exception:
                has_attachments = False

            if has_attachments:
                tool_config = tool_executor.build_tool_config()

                def _tool_exec(name: str, tool_input: dict) -> dict:
                    return tool_executor.execute_tool(name, tool_input, conv_id)

                stream = astream_chat_with_tools(
                    api_messages,
                    model,
                    system_prompt,
                    thinking_enabled=use_thinking,
                    tool_config=tool_config,
                    tool_executor_fn=_tool_exec,
                    max_iterations=TOOL_USE_MAX_ITERATIONS,
                )
            else:
                stream = astream_chat(
                    api_messages,
                    model,
                    system_prompt,
                    thinking_enabled=use_thinking,
                )

            stream_interrupted = False
            async for event_type, chunk in stream:
                # 취소 확인
                async with self:
                    if self._cancel_requested:
                        stream_interrupted = True
                        break

                if event_type == "thinking":
                    async with self:
                        self.is_thinking = True
                elif event_type == "text":
                    content += chunk
                    async with self:
                        self.is_thinking = False
                        self.streaming_content = content
                elif event_type == "tool_use":
                    async with self:
                        self.is_thinking = True  # 검색 중임을 표시
                elif event_type == "tool_result":
                    # 검색 결과는 LLM 이 다음 턴에서 활용 → UI 에 직접 표시 안 함
                    pass
                elif event_type == "usage":
                    input_tokens += int(chunk.get("inputTokens", 0) or 0)
                    output_tokens += int(chunk.get("outputTokens", 0) or 0)

        except Exception as e:
            content = "오류가 발생했습니다."

        finally:
            # 사고 과정 제거 (Nova 등 확장 사고 미지원 모델용)
            content = response_filter.strip_thinking(content)

            # 중단된 경우 접미사 추가
            if stream_interrupted and content:
                content += "\n\n*[생성이 중단되었습니다]*"

            # 3. 최종 AI 메시지를 대화에 저장 + 상태 복구
            async with self:
                self._cancel_requested = False
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
                elif idx is not None and stream_interrupted:
                    # 텍스트 도착 전에 중단된 경우
                    ai_msg = Message(
                        role="assistant",
                        content="*[생성이 시작되기 전에 중단되었습니다]*",
                        timestamp=time.time(),
                        model_name=model_name,
                    )
                    updated = [*self.conversations[idx].messages, ai_msg]
                    self._update_conversation(idx, messages=updated)

                self.is_loading = False
                self.is_thinking = False
                self.streaming_content = ""

        # DB 저장: AI 응답 메시지 (State 락 밖) — 텍스트 없이 중단된 경우 저장 안 함
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

        # 4. 첫 메시지 교환 후 LLM으로 제목 생성
        if is_first_msg and content and emp_no:
            try:
                generated = generate_title(text, content)
                if generated:
                    chat_service.update_conversation_title(conv_id, generated, emp_no)
                    async with self:
                        idx = self._get_current_index()
                        if idx is not None:
                            self._update_conversation(idx, title=generated)
            except Exception:
                pass
