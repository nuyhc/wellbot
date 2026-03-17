"""LLM API 호출 모듈 (Bedrock Converse API)"""
from collections.abc import Generator
from ..config.settings import bedrock_client


def stream_converse(
    messages: list[tuple[str, str]],
    current_question: str,
    model_id: str,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    top_p: float | None = None,
    system_prompt: str | None = None,
) -> Generator[str, None, None]:
    api_messages = []
    for q, a in messages:
        api_messages.append({"role": "user", "content": [{"text": q}]})
        if a:
            api_messages.append({"role": "assistant", "content": [{"text": a}]})
    api_messages.append({"role": "user", "content": [{"text": current_question}]})

    inference_config: dict = {"maxTokens": max_tokens, "temperature": temperature}
    if top_p is not None:
        inference_config["topP"] = top_p

    kwargs: dict = {
        "modelId": model_id,
        "messages": api_messages,
        "inferenceConfig": inference_config,
    }
    if system_prompt:
        kwargs["system"] = [{"text": system_prompt}]

    response = bedrock_client.converse_stream(**kwargs)

    for event in response["stream"]:
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"]["delta"]
            if "text" in delta:
                yield delta["text"]
