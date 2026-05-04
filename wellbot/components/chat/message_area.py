"""메시지 표시 영역 컴포넌트.

대화 메시지 목록, 스트리밍 응답, 사고 과정 인디케이터, 환영 메시지.
자동 스크롤: 하단 근처에 있으면 새 메시지 시 자동 스크롤, 위로 스크롤하면 중단.
"""

import reflex as rx

from wellbot.components.chat.message_bubble import message_bubble
from wellbot.components.icons import north_star_icon
from wellbot.state.chat_state import ChatState
from wellbot.styles import COLORS, MARKDOWN_COMPONENT_MAP, SPACING


def welcome_message() -> rx.Component:
    """대화가 비어있을 때 표시되는 환영 화면."""
    return rx.center(
        rx.vstack(
            rx.box(
                north_star_icon(size=36),
                color=COLORS["text_primary"],
                margin_bottom="0.5em",
            ),
            rx.heading(
                ChatState.greeting_text,
                size="6",
                color=COLORS["text_primary"],
                weight="medium",
            ),
            align="center",
            spacing="2",
        ),
        flex="1",
    )


def loading_indicator() -> rx.Component:
    """AI 응답 대기 중 로딩 인디케이터 (스트리밍 시작 전)."""
    return rx.hstack(
        rx.box(
            rx.icon("message-circle-dashed", size=18, color=COLORS["accent"]),
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
            rx.icon("message-circle-dashed", size=18, color=COLORS["accent"]),
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
            component_map=MARKDOWN_COMPONENT_MAP,
        ),
        width="100%",
        color=COLORS["text_primary"],
        padding_x="1em",
    )


def _nav_button(icon_name: str, btn_id: str, tooltip: str) -> rx.Component:
    """메시지 네비게이션 개별 버튼."""
    return rx.tooltip(
        rx.el.button(
            rx.icon(icon_name, size=16, color=COLORS["text_secondary"]),
            id=btn_id,
            style={
                "width": "32px",
                "height": "32px",
                "border_radius": "50%",
                "background": str(COLORS["input_bg"]),
                "border": f"1px solid {COLORS['border']}",
                "display": "flex",
                "align_items": "center",
                "justify_content": "center",
                "cursor": "pointer",
                "padding": "0",
                "outline": "none",
                "transition": "all 0.15s ease",
                "opacity": "0.7",
                "&:hover": {
                    "opacity": "1",
                    "background": str(COLORS["sidebar_hover"]),
                },
                "&:disabled": {
                    "opacity": "0.3",
                    "cursor": "default",
                },
            },
        ),
        content=tooltip,
    )


def message_nav_panel() -> rx.Component:
    """메시지 네비게이션 패널 (이전/다음/최하단).

    input_bar 우측에 배치되는 VStack 형태.
    visibility로 표시를 제어하여 항상 레이아웃 공간을 확보한다.
    """
    return rx.box(
        rx.vstack(
            _nav_button("chevron-up", "nav-prev-msg", "이전 메시지"),
            _nav_button("chevron-down", "nav-next-msg", "다음 메시지"),
            _nav_button("chevrons-down", "nav-scroll-bottom", "최하단으로"),
            spacing="1",
            align="center",
        ),
        id="msg-nav-panel",
        padding="0.35em",
        border_radius="20px",
        background=COLORS["sidebar_bg"],
        border=f"1px solid {COLORS['border']}",
        box_shadow="0 2px 12px rgba(0,0,0,0.18)",
        flex_shrink="0",
        margin_bottom="2.5em",
        margin_right="0.5em",
        # 초기 상태: 항상 표시
        visibility="visible",
        opacity="1",
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
        padding_top="1em",
        position="relative",
        transition="all 0.2s ease",
    )
