"""로그 상관관계(correlation) 컨텍스트.

멀티유저 챗봇 운영에서 "어떤 사용자의 어떤 대화·요청에서 발생한 로그인가"를
추적할 수 있도록, `contextvars` 로 요청 단위 컨텍스트를 보관한다.

`ContextFilter` 가 모든 LogRecord 에 이 값을 자동 주입하므로,
각 로깅 호출부에서 emp_no/conversation_id 를 인자로 넘길 필요가 없다.

사용:
    # API 미들웨어 / State 이벤트 핸들러 진입부
    from wellbot import log_context
    log_context.bind(emp_no="12345", conversation_id="abc")

    # 요청 종료 시 (또는 with 블록으로 자동 정리)
    with log_context.scope(request_id="req-1", emp_no="12345"):
        ...
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Generator

# 미설정 시 포매터에서 "-" 로 표시되는 기본값
_EMPTY = "-"

_emp_no: ContextVar[str] = ContextVar("emp_no", default=_EMPTY)
_conversation_id: ContextVar[str] = ContextVar("conversation_id", default=_EMPTY)
_request_id: ContextVar[str] = ContextVar("request_id", default=_EMPTY)

_FIELDS = ("emp_no", "conversation_id", "request_id")
_VARS = {
    "emp_no": _emp_no,
    "conversation_id": _conversation_id,
    "request_id": _request_id,
}


def new_request_id() -> str:
    """짧은 요청 ID 를 생성한다 (uuid4 앞 8자)."""
    return uuid.uuid4().hex[:8]


def bind(**fields: str | None) -> dict[str, Token]:
    """컨텍스트 값을 설정하고 복원용 토큰을 반환한다.

    None 인 값은 무시한다. 반환된 토큰 dict 는 `reset()` 에 넘겨 복원한다.
    """
    tokens: dict[str, Token] = {}
    for key, value in fields.items():
        if value is None:
            continue
        var = _VARS.get(key)
        if var is not None:
            tokens[key] = var.set(str(value))
    return tokens


def reset(tokens: dict[str, Token]) -> None:
    """`bind()` 로 받은 토큰으로 이전 컨텍스트를 복원한다."""
    for key, token in tokens.items():
        var = _VARS.get(key)
        if var is not None:
            var.reset(token)


def clear() -> None:
    """모든 컨텍스트 값을 기본값으로 되돌린다."""
    for var in _VARS.values():
        var.set(_EMPTY)


def current() -> dict[str, str]:
    """현재 컨텍스트 스냅샷을 반환한다 (LogRecord 주입용)."""
    return {field: _VARS[field].get() for field in _FIELDS}


@contextmanager
def scope(**fields: str | None) -> Generator[None, None, None]:
    """with 블록 동안만 컨텍스트를 적용하고 자동 복원한다.

    request_id 를 명시하지 않으면 자동 생성한다.
    """
    if "request_id" not in fields or fields.get("request_id") is None:
        fields["request_id"] = new_request_id()
    tokens = bind(**fields)
    try:
        yield
    finally:
        reset(tokens)
