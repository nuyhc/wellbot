"""메시지 버블 컴포넌트.

ChatGPT/Gemini 스타일 메시지 표시.
사용자: 우측 정렬, 둥근 배경 버블.
AI: 좌측 정렬, 배경 없이 마크다운 렌더링.
"""

import reflex as rx

from wellbot.state.chat_state import Message
from wellbot.styles import COLORS, SPACING


def user_message(message: Message) -> rx.Component:
    """사용자 메시지 - 우측 정렬, 둥근 버블."""
    return rx.hstack(
        rx.spacer(),
        rx.box(
            rx.text(
                message.content,
                size="3",
                color=COLORS["text_primary"],
                white_space="pre-wrap",
                word_break="break-word",
            ),
            bg=COLORS["user_bubble"],
            padding="0.75em 1.25em",
            border_radius=SPACING["border_radius"],
            max_width="70%",
        ),
        width="100%",
        justify="end",
        padding_x="1em",
    )


def ai_message(message: Message) -> rx.Component:
    """AI 메시지 - 좌측 정렬, 아이콘 + 마크다운."""
    return rx.hstack(
        # AI 아이콘
        rx.box(
            rx.icon("sparkles", size=18, color=COLORS["accent"]),
            width="30px",
            height="30px",
            border_radius="50%",
            bg=COLORS["user_bubble"],
            display="flex",
            align_items="center",
            justify_content="center",
            flex_shrink="0",
            margin_top="2px",
        ),
        # 메시지 내용 - 마크다운 렌더링
        rx.box(
            rx.markdown(
                message.content,
                component_map={
                    "code": lambda text: rx.code(
                        text,
                        color_scheme="gray",
                        variant="ghost",
                    ),
                },
            ),
            flex="1",
            min_width="0",
            color=COLORS["text_primary"],
        ),
        width="100%",
        align="start",
        spacing="3",
        padding_x="1em",
    )


def message_bubble(message: Message) -> rx.Component:
    """개별 메시지 - 역할에 따라 분기."""
    return rx.cond(
        message.role == "user",
        user_message(message),
        ai_message(message),
    )
