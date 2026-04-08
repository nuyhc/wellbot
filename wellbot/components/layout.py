"""2단 레이아웃 컴포넌트.

Sidebar(좌) + 메인 대화 영역(우) 구성.
반응형 처리: 768px 미만에서 Sidebar 숨김.
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
            color_scheme="gray",
            cursor="pointer",
            on_click=UIState.toggle_sidebar,
            position="fixed",
            top="1em",
            left="1em",
            z_index="10",
        ),
    )


def chat_layout(main_content: rx.Component) -> rx.Component:
    """2단 레이아웃: Sidebar + 메인 영역."""
    return rx.hstack(
        sidebar(),
        rx.box(
            sidebar_toggle_button(),
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
    )
