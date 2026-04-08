"""Sidebar 컴포넌트.

대화 목록, 새 대화 버튼, 사용자 프로필 영역을 포함한다.
"""

import reflex as rx

from wellbot.components.sidebar.conversation_list import conversation_list
from wellbot.state.chat_state import ChatState
from wellbot.state.ui_state import UIState
from wellbot.styles import COLORS, SPACING


def sidebar_header() -> rx.Component:
    """Sidebar 상단: 새 대화 버튼 + pin/hide 토글."""
    return rx.hstack(
        rx.button(
            rx.icon("plus", size=16),
            rx.text("새 대화", size="2"),
            variant="soft",
            size="2",
            cursor="pointer",
            on_click=ChatState.create_new_conversation,
            flex="1",
            min_width="0",
        ),
        rx.hstack(
            rx.icon_button(
                rx.cond(
                    UIState.sidebar_pinned,
                    rx.icon("pin", size=14),
                    rx.icon("pin-off", size=14),
                ),
                variant="ghost",
                size="1",
                color_scheme="gray",
                cursor="pointer",
                on_click=rx.cond(
                    UIState.sidebar_pinned,
                    UIState.unpin_sidebar,
                    UIState.pin_sidebar,
                ),
            ),
            rx.icon_button(
                rx.icon("panel-left-close", size=14),
                variant="ghost",
                size="1",
                color_scheme="gray",
                cursor="pointer",
                on_click=UIState.hide_sidebar,
            ),
            spacing="1",
            flex_shrink="0",
        ),
        width="100%",
        align="center",
        spacing="2",
        padding_x="0.75em",
        padding_y="0.75em",
    )


def user_profile_placeholder() -> rx.Component:
    """사용자 프로필 placeholder. Phase 4에서 실제 프로필로 교체."""
    return rx.hstack(
        rx.icon_button(
            rx.icon("user", size=16),
            size="2",
            radius="full",
            variant="soft",
            color_scheme="gray",
            flex_shrink="0",
        ),
        rx.vstack(
            rx.text("사용자", size="2", weight="medium"),
            rx.text(
                "user@example.com",
                size="1",
                color=COLORS["text_secondary"],
                overflow="hidden",
                text_overflow="ellipsis",
                white_space="nowrap",
            ),
            spacing="0",
            min_width="0",
            flex="1",
        ),
        width="100%",
        align="center",
        spacing="2",
        padding="0.75em",
        border_top=f"1px solid {COLORS['border']}",
    )


def sidebar() -> rx.Component:
    """Sidebar 메인 컴포넌트."""
    return rx.box(
        rx.vstack(
            sidebar_header(),
            rx.separator(color_scheme="gray"),
            conversation_list(),
            user_profile_placeholder(),
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
