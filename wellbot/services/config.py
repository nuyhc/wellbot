"""앱 설정 로드.

config/models.yaml에서 모델 정의를, config/prompts.yaml에서 프롬프트 설정을 읽어온다.
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


_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "models.yaml"
_PROMPTS_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "prompts.yaml"
_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "prompts"

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


def load_config(path: Path | None = None) -> AppConfig:
    """YAML 파일에서 설정을 로드한다."""
    if path is None:
        path = _CONFIG_PATH

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    models = tuple(ModelConfig(**m) for m in raw.get("models", []))
    system_prompt, prompts = _load_prompt_config()

    return AppConfig(
        system_prompt=system_prompt,
        models=models,
        prompts=prompts,
    )


def get_config() -> AppConfig:
    """캐싱된 앱 설정을 반환한다."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
