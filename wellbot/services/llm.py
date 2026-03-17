"""LLM API 호출 모듈 (Bedrock Converse API)"""
from collections.abc import Generator
from ..config.settings import bedrock_client

# tiktoken 미설치 환경용 간이 토큰 추정 (문자 수 / 3)
def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 3)


def trim_history(
    history: list[tuple[str, str]],
    current_question: str,
    context_window: int,
    system_prompt: str | None = None,
) -> list[tuple[str, str]]:
    """대화 이력이 컨텍스트 윈도우 70%를 초과하면 슬라이딩 윈도우 적용.
    이력에 할당된 예산: context_window * 50%
    """
    history_budget = int(context_window * 0.5)

    # 현재 질문 + 시스템 프롬프트 토큰 선 공제
    used = _estimate_tokens(current_question)
    if system_prompt:
        used += _estimate_tokens(system_prompt)

    # 이력 총 토큰 계산 (응답 포함)
    total_history_tokens = sum(
        _estimate_tokens(q) + _estimate_tokens(a) for q, a in history
    )

    # 70% 임계값 미만이면 그대로 반환
    if used + total_history_tokens < context_window * 0.7:
        return history

    # 슬라이딩 윈도우: 오래된 것부터 제거해 budget 안에 맞춤
    trimmed = list(history)
    while trimmed:
        total = sum(_estimate_tokens(q) + _estimate_tokens(a) for q, a in trimmed)
        if total <= history_budget:
            break
        trimmed.pop(0)

    return trimmed


def stream_converse(
    messages: list[tuple[str, str]],
    current_question: str,
    model_id: str,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    top_p: float | None = None,
    system_prompt: str | None = None,
    thinking_enabled: bool = False,
    thinking_budget: int = 5000,
) -> Generator[str, None, None]:
    api_messages = []
    for q, a in messages:
        api_messages.append({"role": "user", "content": [{"text": q}]})
        if a:
            api_messages.append({"role": "assistant", "content": [{"text": a}]})
    api_messages.append({"role": "user", "content": [{"text": current_question}]})

    if thinking_enabled:
        # thinking 요구사항: temperature=1.0, topP 사용 불가, maxTokens >= budget + 출력
        inference_config: dict = {
            "maxTokens": max_tokens + thinking_budget,
            "temperature": 1.0,
        }
    else:
        inference_config = {"maxTokens": max_tokens, "temperature": temperature}
        if top_p is not None:
            inference_config["topP"] = top_p

    kwargs: dict = {
        "modelId": model_id,
        "messages": api_messages,
        "inferenceConfig": inference_config,
    }
    if system_prompt:
        kwargs["system"] = [{"text": system_prompt}]
    if thinking_enabled:
        kwargs["additionalModelRequestFields"] = {
            "thinking": {"type": "enabled", "budget_tokens": thinking_budget}
        }

    response = bedrock_client.converse_stream(**kwargs)

    for event in response["stream"]:
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"]["delta"]
            if "text" in delta:
                yield delta["text"]
            # thinking_delta는 무시 (내부 추론 과정)
