"""Sidebar 컴포넌트.

ChatGPT/Gemini 스타일 사이드바.
대화 목록, 새 대화 버튼, 하단 사용자 프로필.
"""

import reflex as rx

from wellbot.components.sidebar.conversation_list import conversation_list
from wellbot.state.auth_state import AuthState
from wellbot.state.chat_state import ChatState
from wellbot.state.ui_state import UIState
from wellbot.styles import COLORS, SPACING


def sidebar_header() -> rx.Component:
    """Sidebar 상단: 사이드바 토글 + 새 대화 버튼."""
    return rx.hstack(
        rx.icon_button(
            rx.icon("panel-left-close", size=18),
            variant="ghost",
            size="2",
            cursor="pointer",
            on_click=UIState.hide_sidebar,
            color=COLORS["text_secondary"],
            _hover={"color": COLORS["text_primary"]},
        ),
        rx.spacer(),
        rx.icon_button(
            rx.icon("square-pen", size=18),
            variant="ghost",
            size="2",
            cursor="pointer",
            on_click=ChatState.create_new_conversation,
            color=COLORS["text_secondary"],
            _hover={"color": COLORS["text_primary"]},
        ),
        width="100%",
        align="center",
        padding_x="0.75em",
        padding_y="0.75em",
    )


def search_box() -> rx.Component:
    """사이드바 검색 박스."""
    return rx.box(
        rx.hstack(
            rx.icon("search", size=14, color=COLORS["text_secondary"]),
            rx.text("채팅 검색", size="2", color=COLORS["text_secondary"]),
            align="center",
            spacing="2",
            padding_x="0.75em",
            padding_y="0.5em",
            width="100%",
            border_radius=SPACING["border_radius_sm"],
            bg=COLORS["sidebar_hover"],
            cursor="pointer",
            _hover={"bg": COLORS["sidebar_active"]},
        ),
        padding_x="0.5em",
        padding_bottom="0.5em",
        width="100%",
    )


def user_profile() -> rx.Component:
    """인증된 사용자 정보 + 로그아웃."""
    return rx.hstack(
        rx.box(
            rx.icon("user", size=16, color=COLORS["text_primary"]),
            width="28px",
            height="28px",
            border_radius="50%",
            bg=COLORS["sidebar_hover"],
            display="flex",
            align_items="center",
            justify_content="center",
            flex_shrink="0",
        ),
        rx.vstack(
            rx.text(
                AuthState.current_user_nm,
                size="2",
                color=COLORS["text_primary"],
                weight="medium",
            ),
            rx.text(
                AuthState.current_emp_no,
                size="1",
                color=COLORS["text_secondary"],
            ),
            spacing="0",
        ),
        rx.spacer(),
        rx.icon_button(
            rx.icon("log-out", size=14),
            variant="ghost",
            size="1",
            cursor="pointer",
            on_click=AuthState.logout,
            color=COLORS["text_secondary"],
            _hover={"color": COLORS["text_primary"]},
        ),
        width="100%",
        align="center",
        spacing="2",
        padding="0.75em",
        border_radius=SPACING["border_radius_sm"],
    )


def sidebar_footer() -> rx.Component:
    """사이드바 하단 영역."""
    return rx.box(
        rx.separator(color_scheme="gray", size="4"),
        rx.box(
            user_profile(),
            padding_x="0.5em",
            padding_y="0.5em",
        ),
        width="100%",
        flex_shrink="0",
    )


def sidebar() -> rx.Component:
    """Sidebar 메인 컴포넌트."""
    return rx.box(
        rx.vstack(
            sidebar_header(),
            search_box(),
            conversation_list(),
            sidebar_footer(),
            height="100%",
            width="100%",
            spacing="0",
        ),
        bg=COLORS["sidebar_bg"],
        width=SPACING["sidebar_width"],
        min_width=SPACING["sidebar_width"],
        max_width=SPACING["sidebar_width"],
        height="100vh",
        border_right=f"1px solid {COLORS['border']}",
        display=rx.cond(UIState.sidebar_visible, "flex", "none"),
        flex_direction="column",
        overflow="hidden",
    )
