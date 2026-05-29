"""경량 모델 기반 대화 제목 생성."""

from __future__ import annotations

from wellbot.constants import (
    TITLE_MAX_TOKENS,
    TITLE_MODEL_ID,
    TITLE_SYSTEM_PROMPT,
    TITLE_TEMPERATURE,
)
from wellbot.services.ai.bedrock.client import get_client


def generate_title(user_msg: str, assistant_msg: str) -> str:
    """경량 모델로 대화 제목을 생성한다."""
    client = get_client()
    messages = [
        {
            "role": "user",
            "content": [{"text": f"질문: {user_msg}\n\n답변: {assistant_msg}"}],
        },
    ]
    try:
        response = client.converse(
            modelId=TITLE_MODEL_ID,
            messages=messages,
            system=[{"text": TITLE_SYSTEM_PROMPT}],
            inferenceConfig={"maxTokens": TITLE_MAX_TOKENS, "temperature": TITLE_TEMPERATURE},
        )
        output = response.get("output", {})
        content = output.get("message", {}).get("content", [])
        if content and "text" in content[0]:
            return content[0]["text"].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""
