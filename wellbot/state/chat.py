"""채팅 상태 관리 모듈"""
import uuid
import reflex as rx
from wellbot.config.loader import get_models_map, get_model_names, get_system_prompt
from wellbot.services.llm import stream_converse, trim_history
from wellbot.services.file_validator import classify_file, validate_file
from wellbot.services.content_block_builder import AttachedFile, build_content_blocks
from wellbot.services.upstage_dp import parse_document

# 하단으로 강제 스크롤 (메시지 전송 시)
_SCROLL_DOWN = """
const el = document.getElementById("chat-area");
if (el) { el.scrollTop = el.scrollHeight; }
"""

# 하단 근처일 때만 스크롤 (스트리밍 중 — 사용자가 위로 스크롤했으면 방해하지 않음)
_SCROLL_IF_NEAR_BOTTOM = """
const el = document.getElementById("chat-area");
if (el) {
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    if (isNearBottom) { el.scrollTop = el.scrollHeight; }
}
"""

MODEL_NAMES = get_model_names()
MODELS_MAP = get_models_map()
GLOBAL_SYSTEM_PROMPT = get_system_prompt()


class ChatState(rx.State):
    """채팅 관련 상태"""
    question: str = ""
    chat_history: list[tuple[str, str]] = []
    processing: bool = False
    selected_model: str = MODEL_NAMES[0] if MODEL_NAMES else ""
    # 첨부 파일 메타데이터 (UI 렌더링용, 직렬화 가능)
    attached_files: list[dict] = []
    # 파일 바이트 데이터 (언더스코어 접두사로 Reflex 직렬화에서 자동 제외)
    _file_data: dict[str, bytes] = {}
    # 업로드 에러 메시지
    upload_error: str = ""
    uploading: bool = False
    thinking_enabled: bool = False

    # 대화 관리 (인메모리)
    current_conversation_id: str = ""
    conversations: dict[str, dict] = {}  # {id: {title, history, model}}
    conversation_order: list[str] = []   # 최신순 ID 목록 (rx.foreach용)

    @rx.var
    def current_model_supports_thinking(self) -> bool:
        return bool(MODELS_MAP.get(self.selected_model, {}).get("thinking", False))

    @rx.var
    def conversation_list(self) -> list[dict[str, str]]:
        """사이드바 렌더링용 대화 목록"""
        result = []
        for conv_id in self.conversation_order:
            conv = self.conversations.get(conv_id, {})
            result.append({
                "id": conv_id,
                "title": conv.get("title", "New Chat"),
                "is_active": "true" if conv_id == self.current_conversation_id else "false",
            })
        return result

    def _ensure_conversation(self):
        """대화 ID가 없으면 자동 생성 (lazy init)"""
        if not self.current_conversation_id:
            new_id = str(uuid.uuid4())
            self.current_conversation_id = new_id
            self.conversations[new_id] = {
                "title": "New Chat",
                "history": [],
                "model": self.selected_model,
            }
            self.conversation_order.insert(0, new_id)

    def new_chat(self):
        """현재 대화 저장 → 새 빈 대화 생성"""
        if self.processing:
            return

        # 현재 대화 히스토리를 레지스트리에 저장
        if self.current_conversation_id and self.chat_history:
            self.conversations[self.current_conversation_id]["history"] = [
                list(pair) for pair in self.chat_history
            ]
            self.conversations[self.current_conversation_id]["model"] = self.selected_model

        # 현재 대화가 비어있으면 새로 만들지 않음 (중복 방지)
        if self.current_conversation_id and not self.chat_history:
            return

        # 새 대화 생성
        new_id = str(uuid.uuid4())
        self.current_conversation_id = new_id
        self.conversations[new_id] = {
            "title": "New Chat",
            "history": [],
            "model": self.selected_model,
        }
        self.conversation_order.insert(0, new_id)

        # 활성 채팅 상태 초기화
        self.chat_history = []
        self.question = ""
        self.attached_files = []
        self._file_data = {}
        self.upload_error = ""

    def switch_conversation(self, conv_id: str):
        """기존 대화로 전환"""
        if self.processing:
            return
        if conv_id == self.current_conversation_id:
            return

        # 현재 대화 저장
        if self.current_conversation_id:
            self.conversations[self.current_conversation_id]["history"] = [
                list(pair) for pair in self.chat_history
            ]
            self.conversations[self.current_conversation_id]["model"] = self.selected_model

        # 대상 대화 로드
        conv = self.conversations.get(conv_id)
        if not conv:
            return

        self.current_conversation_id = conv_id
        self.chat_history = [tuple(pair) for pair in conv["history"]]
        self.selected_model = conv.get("model", self.selected_model)

        # 임시 상태 초기화
        self.question = ""
        self.attached_files = []
        self._file_data = {}
        self.upload_error = ""

    def delete_conversation(self, conv_id: str):
        """대화 삭제"""
        if self.processing:
            return

        self.conversations.pop(conv_id, None)
        if conv_id in self.conversation_order:
            self.conversation_order.remove(conv_id)

        # 활성 대화를 삭제한 경우 다음 대화로 전환
        if conv_id == self.current_conversation_id:
            if self.conversation_order:
                next_id = self.conversation_order[0]
                next_conv = self.conversations.get(next_id, {})
                self.current_conversation_id = next_id
                self.chat_history = [tuple(pair) for pair in next_conv.get("history", [])]
                self.selected_model = next_conv.get("model", self.selected_model)
            else:
                self.current_conversation_id = ""
                self.chat_history = []
                self._ensure_conversation()

            self.question = ""
            self.attached_files = []
            self._file_data = {}
            self.upload_error = ""

    def set_question(self, value: str):
        self.question = value

    def set_selected_model(self, value: str):
        self.selected_model = value
        # 모델 변경 시 thinking 지원 안 하면 자동 off
        if not MODELS_MAP.get(value, {}).get("thinking", False):
            self.thinking_enabled = False

    def toggle_thinking(self, value: bool):
        self.thinking_enabled = value

    async def handle_upload(self, files: list[rx.UploadFile]):
        """파일 업로드 처리 — 검증 후 바이트 데이터를 메모리에 저장"""
        # 에러 초기화 (루프 전체에서 마지막 에러만 남지 않도록 루프 밖에서 초기화)
        self.upload_error = ""
        self.uploading = True
        yield

        for file in files:
            if not file.filename:
                continue

            try:
                # 파일 바이트를 메모리에서 읽기 (디스크 저장 없음)
                file_bytes = await file.read()

                # 파일 타입 분류
                file_type = classify_file(file.filename)

                # 현재 이미지/문서 개수 계산 — 동일 파일명은 교체 대상이므로 제외
                current_image_count = sum(
                    1 for f in self.attached_files
                    if f["file_type"] == "image" and f["filename"] != file.filename
                )
                current_document_count = sum(
                    1 for f in self.attached_files
                    if f["file_type"] in ("document", "presentation", "parsed_text")
                    and f["filename"] != file.filename
                )

                # 크기 및 개수 검증
                validate_file(
                    filename=file.filename,
                    file_size=len(file_bytes),
                    current_image_count=current_image_count,
                    current_document_count=current_document_count,
                )

                # 프레젠테이션 파일은 Upstage DP로 파싱하여 텍스트로 변환
                if file_type == "presentation":
                    parsed_text = await parse_document(file_bytes, file.filename)
                    file_bytes = parsed_text.encode("utf-8")
                    file_type = "parsed_text"

                # 중복 파일명 처리 (덮어쓰기)
                self.attached_files = [
                    f for f in self.attached_files if f["filename"] != file.filename
                ]

                # 검증 성공: 메타데이터 및 바이트 저장
                self.attached_files.append(
                    {"filename": file.filename, "file_type": file_type}
                )
                self._file_data[file.filename] = file_bytes

            except ValueError as e:
                # 검증 실패: 에러 메시지 설정
                self.upload_error = str(e)

        self.uploading = False

    def remove_file(self, filename: str):
        """첨부 파일 제거 — 메타데이터와 바이트 데이터 모두 삭제"""
        self.attached_files = [
            f for f in self.attached_files if f["filename"] != filename
        ]
        self._file_data.pop(filename, None)

    async def answer(self):
        if not self.question.strip() and not self.attached_files:
            return

        self._ensure_conversation()

        current_question = self.question.strip()

        # 문서만 첨부하고 텍스트가 비어있으면 기본 텍스트 삽입
        has_document = any(
            f["file_type"] in ("document", "parsed_text") for f in self.attached_files
        )
        if not current_question and has_document:
            current_question = "첨부된 파일을 분석해주세요."

        # 첫 메시지일 때 대화 제목 자동 설정
        if not self.chat_history and self.current_conversation_id:
            title = current_question[:30]
            if len(current_question) > 30:
                title += "..."
            self.conversations[self.current_conversation_id]["title"] = title
            self.conversations = dict(self.conversations)  # re-render 보장

        self.chat_history.append((current_question, ""))
        self.question = ""
        self.processing = True
        yield rx.call_script(_SCROLL_DOWN)

        try:
            # 첨부 파일이 있으면 content block 빌드
            file_blocks: list[dict] | None = None
            if self.attached_files and self._file_data:
                attached = [
                    AttachedFile(
                        filename=f["filename"],
                        data=self._file_data[f["filename"]],
                        file_type=f["file_type"],
                    )
                    for f in self.attached_files
                    if f["filename"] in self._file_data
                ]
                blocks, failed = build_content_blocks(attached)
                if blocks:
                    file_blocks = blocks
                if failed:
                    self.upload_error = (
                        "일부 파일(" + ", ".join(failed) + ")을 처리할 수 없어 제외되었습니다."
                    )

            model_cfg = MODELS_MAP.get(self.selected_model)
            if not model_cfg:
                model_cfg = list(MODELS_MAP.values())[0]

            system_prompt = model_cfg.get("system_prompt") or GLOBAL_SYSTEM_PROMPT
            history = trim_history(
                history=self.chat_history[:-1],
                current_question=current_question,
                context_window=model_cfg.get("context_window", 200000),
                system_prompt=system_prompt,
            )

            for token in stream_converse(
                messages=history,
                current_question=current_question,
                model_id=model_cfg["model_id"],
                max_tokens=model_cfg.get("max_tokens", 1024),
                temperature=model_cfg.get("temperature", 0.7),
                top_p=model_cfg.get("top_p"),
                system_prompt=system_prompt,
                thinking_enabled=self.thinking_enabled,
                thinking_budget=model_cfg.get("thinking_budget", 5000),
                file_blocks=file_blocks,
            ):
                q, current = self.chat_history[-1]
                self.chat_history[-1] = (q, current + token)
                yield rx.call_script(_SCROLL_IF_NEAR_BOTTOM)

        except Exception as e:
            import traceback
            print(f"LLM INVOCATION ERROR: {e}")
            traceback.print_exc()
            self.chat_history[-1] = (
                self.chat_history[-1][0],
                f"오류가 발생했습니다: {e}"
            )
            yield rx.call_script(_SCROLL_DOWN)

        finally:
            # 전송 완료 후 첨부 파일 초기화 (메모리 해제)
            self.attached_files = []
            self._file_data = {}
            self.processing = False

            # 대화 레지스트리에 히스토리 동기화
            if self.current_conversation_id:
                self.conversations[self.current_conversation_id]["history"] = [
                    list(pair) for pair in self.chat_history
                ]
            yield
