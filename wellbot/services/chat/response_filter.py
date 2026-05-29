"""응답 텍스트 후처리 필터.

LLM 이 사고 과정(chain-of-thought)을 일반 텍스트로 출력하는 경우를 감지하고 제거.
확장 사고(extended thinking)를 지원하지 않는 모델(Nova 계열)에서 발생.

패턴:
  1. <thinking>...</thinking> 등 사고 명시 태그
  2. 응답 시작부의 영어 사고 과정 (한국어 답변 앞)
"""

from __future__ import annotations

import re

# 1. XML 태그 기반 사고 과정 제거
_THINKING_TAG_PATTERN = re.compile(
    r"<(?:thinking|chain_of_thought|reasoning|thought|inner_monologue)>"
    r".*?"
    r"</(?:thinking|chain_of_thought|reasoning|thought|inner_monologue)>",
    re.DOTALL | re.IGNORECASE,
)

# 2. 영어 사고 과정 문장 패턴 (응답 시작부에서만)
#    "The user wants...", "I should...", "I need to...", "Let me..." 등
_THINKING_SENTENCE_STARTERS = re.compile(
    r"^("
    r"(?:The user (?:wants|is asking|has requested|would like|seems to).*?[.!]\s*)+"
    r"|(?:I (?:should|need to|will|must|can|cannot|don't have).*?[.!]\s*)+"
    r"|(?:Let me (?:check|think|look|analyze|search|find).*?[.!]\s*)+"
    r"|(?:This (?:is|seems|appears|looks like|means).*?[.!]\s*)+"
    r")+",
    re.MULTILINE,
)


def strip_thinking(text: str) -> str:
    """응답 텍스트에서 사고 과정을 제거한다.

    Args:
        text: LLM 응답 원문.

    Returns:
        사고 과정이 제거된 텍스트. 제거할 것이 없으면 원문 그대로.
    """
    if not text:
        return text

    result = text

    # 1단계: XML 태그 제거
    result = _THINKING_TAG_PATTERN.sub("", result)

    # 2단계: 응답 시작부의 영어 사고 과정 제거
    # 조건: 제거 후에도 실질적인 내용이 남아있어야 함
    stripped = result.strip()
    match = _THINKING_SENTENCE_STARTERS.match(stripped)
    if match:
        remaining = stripped[match.end():].strip()
        # 실제 답변이 남아있을 때만 제거 (전체가 영어 답변일 수 있으므로)
        if remaining and len(remaining) > 20:
            result = remaining

    return result.strip()
