"""메시지 표시 영역 컴포넌트.

ChatGPT/Gemini 스타일 메시지 영역.
대화 메시지 목록, 스트리밍 응답, 사고 과정 인디케이터, 환영 메시지.
"""

import reflex as rx

from wellbot.components.chat.message_bubble import message_bubble
from wellbot.state.chat_state import ChatState
from wellbot.styles import COLORS, SPACING


def welcome_message() -> rx.Component:
    """대화가 비어있을 때 표시되는 환영 메시지."""
    return rx.center(
        rx.vstack(
            rx.box(
                rx.icon("wand", size=32, color=COLORS["accent"]),
                width="56px",
                height="56px",
                border_radius="50%",
                bg=COLORS["user_bubble"],
                display="flex",
                align_items="center",
                justify_content="center",
            ),
            rx.heading(
                "무엇을 도와드릴까요?",
                size="6",
                color=COLORS["text_primary"],
                weight="medium",
            ),
            align="center",
            spacing="4",
        ),
        flex="1",
    )


def loading_indicator() -> rx.Component:
    """AI 응답 대기 중 로딩 인디케이터 (스트리밍 시작 전)."""
    return rx.hstack(
        rx.box(
            rx.icon("wand", size=18, color=COLORS["accent"]),
            width="30px",
            height="30px",
            border_radius="50%",
            bg=COLORS["user_bubble"],
            display="flex",
            align_items="center",
            justify_content="center",
            flex_shrink="0",
        ),
        rx.hstack(
            rx.spinner(size="1"),
            rx.text(
                "응답 준비 중...",
                size="2",
                color=COLORS["text_secondary"],
            ),
            spacing="2",
            align="center",
        ),
        width="100%",
        align="start",
        spacing="3",
        padding_x="1em",
    )


def thinking_indicator() -> rx.Component:
    """AI 사고 과정 진행 중 인디케이터 (Extended Thinking)."""
    return rx.hstack(
        rx.box(
            rx.icon("brain", size=18, color=COLORS["accent"]),
            width="30px",
            height="30px",
            border_radius="50%",
            bg=COLORS["user_bubble"],
            display="flex",
            align_items="center",
            justify_content="center",
            flex_shrink="0",
        ),
        rx.hstack(
            rx.spinner(size="1"),
            rx.text(
                "깊이 생각하는 중...",
                size="2",
                color=COLORS["text_secondary"],
            ),
            spacing="2",
            align="center",
        ),
        width="100%",
        align="start",
        spacing="3",
        padding_x="1em",
    )


def streaming_message() -> rx.Component:
    """스트리밍 중인 AI 응답 표시."""
    return rx.box(
        rx.markdown(
            ChatState.streaming_content,
            component_map={
                "code": lambda text: rx.code(
                    text,
                    color_scheme="gray",
                    variant="ghost",
                ),
            },
        ),
        width="100%",
        color=COLORS["text_primary"],
        padding_x="1em",
    )


def message_area() -> rx.Component:
    """메시지 표시 영역."""
    return rx.box(
        rx.cond(
            ChatState.has_messages,
            rx.vstack(
                rx.foreach(
                    ChatState.current_messages,
                    message_bubble,
                ),
                # 스트리밍 중인 텍스트 응답
                rx.cond(ChatState.has_streaming, streaming_message()),
                # Extended Thinking 인디케이터
                rx.cond(
                    ChatState.is_loading & ChatState.is_thinking,
                    thinking_indicator(),
                ),
                # 로딩 인디케이터 (스트리밍/사고 시작 전)
                rx.cond(
                    ChatState.is_loading
                    & ~ChatState.is_thinking
                    & ~ChatState.has_streaming,
                    loading_indicator(),
                ),
                rx.box(id="message-bottom"),
                spacing="4",
                padding_y="1.5em",
                width="100%",
                max_width=SPACING["message_max_width"],
                margin_x="auto",
            ),
            welcome_message(),
        ),
        id="message-area",
        flex="1",
        overflow_y="auto",
        width="100%",
        padding_top="3em",
        transition="all 0.2s ease",
    )
