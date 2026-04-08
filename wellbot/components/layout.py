"""2단 레이아웃 컴포넌트.

ChatGPT/Gemini 스타일 레이아웃.
Sidebar(좌) + 메인 대화 영역(우) + 우측 상단 다크/라이트 모드 토글.
"""

import reflex as rx

from wellbot.components.sidebar.sidebar import sidebar
from wellbot.state.ui_state import UIState
from wellbot.styles import COLORS


def sidebar_toggle_button() -> rx.Component:
    """Sidebar가 숨겨졌을 때 표시되는 토글 버튼."""
    return rx.cond(
        ~UIState.sidebar_visible,
        rx.icon_button(
            rx.icon("panel-left-open", size=18),
            variant="ghost",
            size="2",
            cursor="pointer",
            on_click=UIState.toggle_sidebar,
            position="absolute",
            top="0.75em",
            left="0.75em",
            z_index="10",
            color=COLORS["text_secondary"],
            _hover={"color": COLORS["text_primary"]},
        ),
    )


def color_mode_toggle() -> rx.Component:
    """우측 상단 다크/라이트 모드 전환 버튼."""
    return rx.icon_button(
        rx.color_mode_cond(
            light=rx.icon("moon", size=18),
            dark=rx.icon("sun", size=18),
        ),
        variant="ghost",
        size="2",
        cursor="pointer",
        on_click=rx.toggle_color_mode,
        position="absolute",
        top="0.75em",
        right="0.75em",
        z_index="10",
        color=COLORS["text_secondary"],
        _hover={"color": COLORS["text_primary"]},
    )


def chat_layout(main_content: rx.Component) -> rx.Component:
    """2단 레이아웃: Sidebar + 메인 영역."""
    return rx.hstack(
        sidebar(),
        rx.box(
            sidebar_toggle_button(),
            color_mode_toggle(),
            main_content,
            flex="1",
            height="100vh",
            overflow="hidden",
            bg=COLORS["main_bg"],
            position="relative",
        ),
        height="100vh",
        width="100%",
        spacing="0",
        overflow="hidden",
        bg=COLORS["main_bg"],
    )
