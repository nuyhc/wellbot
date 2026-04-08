"""메시지 표시 영역 컴포넌트.

대화 메시지 목록, 환영 메시지, 로딩 인디케이터를 표시한다.
새 메시지 추가 시 자동으로 최하단으로 스크롤한다.
"""

import reflex as rx

from wellbot.components.chat.message_bubble import message_bubble
from wellbot.state.chat_state import ChatState
from wellbot.styles import COLORS, SPACING


def welcome_message() -> rx.Component:
    """대화가 비어있을 때 표시되는 환영 메시지."""
    return rx.center(
        rx.vstack(
            rx.icon("message-circle", size=48, color=COLORS["accent"]),
            rx.heading("Wellbot에 오신 것을 환영합니다", size="5"),
            rx.text(
                "무엇이든 물어보세요!",
                color=COLORS["text_secondary"],
                size="3",
            ),
            align="center",
            spacing="3",
        ),
        flex="1",
    )


def loading_indicator() -> rx.Component:
    """AI 응답 대기 중 표시되는 로딩 인디케이터."""
    return rx.hstack(
        rx.icon_button(
            rx.icon("bot", size=16),
            size="2",
            radius="full",
            variant="soft",
            color_scheme="blue",
            cursor="default",
        ),
        rx.box(
            rx.hstack(
                rx.spinner(size="1"),
                rx.text("답변을 생성하고 있습니다...", size="2", color=COLORS["text_secondary"]),
                spacing="2",
                align="center",
            ),
            bg=COLORS["ai_bubble"],
            padding="0.75em 1em",
            border_radius=SPACING["border_radius"],
        ),
        width="100%",
        justify="start",
        align="start",
        spacing="2",
        padding_x="1em",
    )


def message_area() -> rx.Component:
    """메시지 표시 영역."""
    return rx.box(
        rx.cond(
            ChatState.has_messages,
            # 메시지가 있을 때
            rx.vstack(
                rx.foreach(
                    ChatState.current_messages,
                    message_bubble,
                ),
                rx.cond(ChatState.is_loading, loading_indicator()),
                # 하단 앵커 (자동 스크롤용)
                rx.box(id="message-bottom"),
                spacing="3",
                padding_y="1em",
                width="100%",
                max_width=SPACING["message_max_width"],
                margin_x="auto",
            ),
            # 메시지가 없을 때
            welcome_message(),
        ),
        id="message-area",
        flex="1",
        overflow_y="auto",
        width="100%",
        padding_bottom=SPACING["input_bar_height"],
    )
