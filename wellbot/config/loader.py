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
            "model_id": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "max_tokens": 1024,
            "temperature": 0.7,
        }
    ]
}

_cached_config: dict | None = None


def load_config() -> dict:
    """config.yaml을 파싱하여 반환 (캐싱)"""
    global _cached_config
    if _cached_config is not None:
        return _cached_config
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            _cached_config = yaml.safe_load(f)
    except FileNotFoundError:
        _cached_config = _DEFAULT_CONFIG
    return _cached_config


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


def get_system_prompt() -> str | None:
    """글로벌 시스템 프롬프트 반환"""
    return load_config().get("system_prompt")


_DEFAULT_FILE_UPLOAD = {"max_file_size": 52428800, "max_file_count": 20, "upload_dir": "uploaded_files"}
_DEFAULT_CONTEXT_BUDGET = {"system_ratio": 0.05, "file_ratio": 0.30, "history_ratio": 0.50, "question_ratio": 0.15}
_DEFAULT_VECTOR_STORE = {"default_k": 5, "retention_days": 30}


def get_file_upload_config() -> dict:
    """file_upload 섹션 반환"""
    return load_config().get("file_upload", _DEFAULT_FILE_UPLOAD)


def get_context_budget_config(model_name: str | None = None) -> dict:
    """context_budget 섹션 반환 (모델별 오버라이드 지원)"""
    cfg = load_config()
    budget = {**_DEFAULT_CONTEXT_BUDGET, **cfg.get("context_budget", {})}
    if model_name:
        model = get_models_map().get(model_name, {})
        if "context_budget" in model:
            budget = {**budget, **model["context_budget"]}
    return budget


def get_vector_store_config() -> dict:
    """vector_store 섹션 반환"""
    return load_config().get("vector_store", _DEFAULT_VECTOR_STORE)
