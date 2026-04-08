"""메시지 버블 컴포넌트.

사용자/AI 메시지를 시각적으로 구분하여 표시한다.
AI 메시지는 마크다운 렌더링을 지원한다.
"""

import reflex as rx

from wellbot.state.chat_state import Message
from wellbot.styles import COLORS, SPACING


def message_bubble(message: Message) -> rx.Component:
    """개별 메시지 버블."""
    is_user = message.role == "user"

    return rx.hstack(
        # AI 아이콘 (좌측)
        rx.cond(
            ~is_user,
            rx.icon_button(
                rx.icon("bot", size=16),
                size="2",
                radius="full",
                variant="soft",
                color_scheme="blue",
                cursor="default",
            ),
            rx.box(),  # 사용자 메시지일 때 빈 공간
        ),
        # 메시지 내용
        rx.box(
            rx.cond(
                is_user,
                # 사용자 메시지: 일반 텍스트
                rx.text(
                    message.content,
                    size="3",
                    white_space="pre-wrap",
                    word_break="break-word",
                ),
                # AI 메시지: 마크다운 렌더링
                rx.markdown(
                    message.content,
                    component_map={
                        "code": lambda text: rx.code(text, color_scheme="blue"),
                    },
                ),
            ),
            bg=rx.cond(is_user, COLORS["user_bubble"], COLORS["ai_bubble"]),
            padding="0.75em 1em",
            border_radius=SPACING["border_radius"],
            max_width="75%",
            word_break="break-word",
        ),
        # 사용자 아이콘 (우측)
        rx.cond(
            is_user,
            rx.icon_button(
                rx.icon("user", size=16),
                size="2",
                radius="full",
                variant="soft",
                color_scheme="gray",
                cursor="default",
            ),
            rx.box(),  # AI 메시지일 때 빈 공간
        ),
        width="100%",
        justify=rx.cond(is_user, "end", "start"),
        align="start",
        spacing="2",
        padding_x="1em",
    )
