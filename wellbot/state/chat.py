"""채팅 상태 관리 모듈"""
import reflex as rx
from ..config.loader import get_models_map, get_model_names
from ..services.llm import stream_claude, stream_nova

MODEL_NAMES = get_model_names()
MODELS_MAP = get_models_map()


class ChatState(rx.State):
    """채팅 관련 상태"""
    question: str = ""
    chat_history: list[tuple[str, str]] = []
    processing: bool = False
    selected_model: str = MODEL_NAMES[0] if MODEL_NAMES else ""

    def set_selected_model(self, value: str):
        self.selected_model = value

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

            model_type = model_cfg.get("type", "claude")

            if model_type == "claude":
                for token in stream_claude(
                    messages=self.chat_history[:-1],
                    current_question=current_question,
                    model_id=model_cfg["model_id"],
                    max_tokens=model_cfg.get("max_tokens", 1024),
                    temperature=model_cfg.get("temperature", 0.7),
                ):
                    q, current = self.chat_history[-1]
                    self.chat_history[-1] = (q, current + token)
                    yield
            elif model_type == "nova":
                for token in stream_nova(
                    messages=self.chat_history[:-1],
                    current_question=current_question,
                    model_id=model_cfg["model_id"],
                    max_tokens=model_cfg.get("max_tokens", 1024),
                    temperature=model_cfg.get("temperature", 0.7),
                    top_p=model_cfg.get("top_p", 0.9),
                ):
                    q, current = self.chat_history[-1]
                    self.chat_history[-1] = (q, current + token)
                    yield
            else:
                raise ValueError(f"Unsupported model type: {model_type}")

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
