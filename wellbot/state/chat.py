"""채팅 상태 관리 모듈"""
import reflex as rx
from wellbot.config.loader import get_models_map, get_model_names, get_system_prompt
from wellbot.services.llm import stream_converse, trim_history

MODEL_NAMES = get_model_names()
MODELS_MAP = get_models_map()
GLOBAL_SYSTEM_PROMPT = get_system_prompt()


class ChatState(rx.State):
    """채팅 관련 상태"""
    question: str = ""
    chat_history: list[tuple[str, str]] = []
    processing: bool = False
    selected_model: str = MODEL_NAMES[0] if MODEL_NAMES else ""
    attached_files: list[str] = []
    thinking_enabled: bool = False

    @rx.var
    def current_model_supports_thinking(self) -> bool:
        return bool(MODELS_MAP.get(self.selected_model, {}).get("thinking", False))

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
        for file in files:
            if file.filename and file.filename not in self.attached_files:
                self.attached_files.append(file.filename)

    def remove_file(self, filename: str):
        self.attached_files = [f for f in self.attached_files if f != filename]

    async def answer(self):
        if not self.question.strip():
            return

        self.chat_history.append((self.question, ""))
        current_question = self.question
        self.question = ""
        self.processing = True
        yield

        try:
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
            ):
                q, current = self.chat_history[-1]
                self.chat_history[-1] = (q, current + token)
                yield

        except Exception as e:
            import traceback
            print(f"LLM INVOCATION ERROR: {e}")
            traceback.print_exc()
            self.chat_history[-1] = (
                self.chat_history[-1][0],
                f"오류가 발생했습니다: {e}"
            )
            yield

        finally:
            self.processing = False
            yield
