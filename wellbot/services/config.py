"""앱 설정 로드.

config/models.yaml에서 모델 정의를, config/prompts.yaml에서 프롬프트 설정 로드.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
import yaml

# .env 파일에서 환경변수 로드 (AWS_REGION 등)
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


@dataclass(frozen=True)
class ModelConfig:
    """개별 모델 설정."""

    name: str
    provider: str
    model_id: str
    context_window: int
    max_tokens: int
    temperature: float
    description: str = ""
    thinking: bool = False
    thinking_budget: int = 0
    top_p: float | None = None
    supports_vision: bool = False      # 이미지 입력 (Converse image block)
    supports_document: bool = False    # document block 입력


@dataclass(frozen=True)
class PromptTemplate:
    """시스템 프롬프트 템플릿."""

    name: str
    content: str
    description: str = ""


@dataclass(frozen=True)
class AppConfig:
    """앱 전체 설정."""

    system_prompt: str
    models: tuple[ModelConfig, ...]
    prompts: tuple[PromptTemplate, ...]
    agent_modes: tuple[AgentMode, ...] = ()

    def get_model(self, name: str) -> ModelConfig | None:
        """이름으로 모델 설정을 찾는다."""
        for m in self.models:
            if m.name == name:
                return m
        return None

    def get_prompt(self, name: str) -> PromptTemplate | None:
        """이름으로 프롬프트 템플릿을 찾는다."""
        for p in self.prompts:
            if p.name == name:
                return p
        return None

    @property
    def default_model(self) -> ModelConfig:
        """첫 번째 모델을 기본값으로 반환한다."""
        return self.models[0]

    @property
    def model_names(self) -> list[str]:
        """모델 이름 목록."""
        return [m.name for m in self.models]

    @property
    def prompt_names(self) -> list[str]:
        """프롬프트 템플릿 이름 목록."""
        return [p.name for p in self.prompts]

    @property
    def agent_mode_ids(self) -> list[str]:
        """에이전트 모드 ID 목록."""
        return [a.id for a in self.agent_modes]

    def get_agent_mode(self, mode_id: str) -> AgentMode | None:
        """ID로 에이전트 모드를 찾는다."""
        for a in self.agent_modes:
            if a.id == mode_id:
                return a
        return None


@dataclass(frozen=True)
class AgentMode:
    """에이전트 모드 설정."""

    id: str
    name: str
    description: str = ""
    icon: str = "message-circle"


_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "models.yaml"
_PROMPTS_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "prompts.yaml"
_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "prompts"
_AGENTS_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "agents.yaml"

_config: AppConfig | None = None


def _load_prompt_config() -> tuple[str, tuple[PromptTemplate, ...]]:
    """config/prompts.yaml과 config/prompts/ 디렉토리에서 프롬프트를 로드한다."""
    # prompts.yaml 읽기
    prompt_entries: list[dict[str, str] | str] = []
    default_prompt = "default"
    if _PROMPTS_CONFIG_PATH.exists():
        with open(_PROMPTS_CONFIG_PATH, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        default_prompt = raw.get("default", "default")
        prompt_entries = raw.get("prompts", [])

    # 순서 설정에서 설명 매핑 구성
    desc_map: dict[str, str] = {}
    order_names: list[str] = []
    for item in prompt_entries:
        if isinstance(item, dict):
            name = item.get("name", "")
            desc_map[name] = item.get("description", "")
            order_names.append(name)
        else:
            order_names.append(item)

    # .md 파일 수집
    by_name: dict[str, PromptTemplate] = {}
    if _PROMPTS_DIR.exists():
        for f in _PROMPTS_DIR.glob("*.md"):
            content = f.read_text(encoding="utf-8").strip()
            by_name[f.stem] = PromptTemplate(
                name=f.stem,
                content=content,
                description=desc_map.get(f.stem, ""),
            )

    # 순서 적용
    if order_names:
        ordered = []
        for name in order_names:
            if name in by_name:
                ordered.append(by_name.pop(name))
        ordered.extend(sorted(by_name.values(), key=lambda p: p.name))
        prompts = tuple(ordered)
    else:
        prompts = tuple(sorted(by_name.values(), key=lambda p: p.name))

    # 기본 시스템 프롬프트 결정
    system_prompt = default_prompt
    for p in prompts:
        if p.name == default_prompt:
            system_prompt = p.content
            break

    return system_prompt, prompts


def _load_agent_modes() -> tuple[AgentMode, ...]:
    """config/agents.yaml에서 에이전트 모드를 로드한다."""
    if not _AGENTS_CONFIG_PATH.exists():
        return (AgentMode(id="chat", name="기본 대화", icon="message-circle"),)
    try:
        with open(_AGENTS_CONFIG_PATH, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        items = raw.get("agent_modes", [])
        return tuple(AgentMode(**item) for item in items) if items else (
            AgentMode(id="chat", name="기본 대화", icon="message-circle"),
        )
    except Exception:
        return (AgentMode(id="chat", name="기본 대화", icon="message-circle"),)


def load_config(path: Path | None = None) -> AppConfig:
    """YAML 파일에서 설정을 로드한다."""
    if path is None:
        path = _CONFIG_PATH

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    models = tuple(ModelConfig(**m) for m in raw.get("models", []))
    system_prompt, prompts = _load_prompt_config()
    agent_modes = _load_agent_modes()

    return AppConfig(
        system_prompt=system_prompt,
        models=models,
        prompts=prompts,
        agent_modes=agent_modes,
    )


def get_config() -> AppConfig:
    """캐싱된 앱 설정을 반환한다."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


# ── 환영 메시지 ──

_GREETINGS_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "greetings.yaml"
_DEFAULT_GREETING = "오늘은 무슨 이야기를 할까요?"
_greetings: tuple[str, ...] | None = None


def get_greetings() -> tuple[str, ...]:
    """캐싱된 환영 메시지 목록을 반환한다."""
    global _greetings
    if _greetings is None:
        try:
            with open(_GREETINGS_PATH, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            items = raw.get("greetings", [])
            _greetings = tuple(items) if items else (_DEFAULT_GREETING,)
        except Exception:
            _greetings = (_DEFAULT_GREETING,)
    return _greetings
