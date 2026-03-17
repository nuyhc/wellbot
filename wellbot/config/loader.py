"""YAML 설정 파일 로딩 모듈"""
import os
import yaml


_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "config.yaml"
)

_DEFAULT_CONFIG = {
    "models": [
        {
            "name": "Claude Sonnet 4.5",
            "provider": "bedrock",
            "type": "claude",
            "model_id": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "max_tokens": 1024,
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 50
        }
    ]
}


def load_config() -> dict:
    """config.yaml을 파싱하여 반환"""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return _DEFAULT_CONFIG


def get_models_config() -> list[dict]:
    """모델 목록 반환"""
    cfg = load_config()
    return cfg.get("models", _DEFAULT_CONFIG["models"])


def get_model_names() -> list[str]:
    """모델 표시명 리스트 반환"""
    return [m["name"] for m in get_models_config()]


def get_models_map() -> dict[str, dict]:
    """모델명 → 설정 dict 매핑 반환"""
    return {m["name"]: m for m in get_models_config()}
