"""모델 설정 로드.

config/models.yaml에서 모델 정의와 시스템 프롬프트를 읽어온다.
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
class AppConfig:
    """앱 전체 설정."""

    system_prompt: str
    models: tuple[ModelConfig, ...]

    def get_model(self, name: str) -> ModelConfig | None:
        """이름으로 모델 설정을 찾는다."""
        for m in self.models:
            if m.name == name:
                return m
        return None

    @property
    def default_model(self) -> ModelConfig:
        """첫 번째 모델을 기본값으로 반환한다."""
        return self.models[0]

    @property
    def model_names(self) -> list[str]:
        """모델 이름 목록."""
        return [m.name for m in self.models]


_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "models.yaml"

_config: AppConfig | None = None


def load_config(path: Path | None = None) -> AppConfig:
    """YAML 파일에서 설정을 로드한다."""
    if path is None:
        path = _CONFIG_PATH

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    models = tuple(ModelConfig(**m) for m in raw.get("models", []))

    return AppConfig(
        system_prompt=raw.get("system_prompt", "").strip(),
        models=models,
    )


def get_config() -> AppConfig:
    """캐싱된 앱 설정을 반환한다."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
