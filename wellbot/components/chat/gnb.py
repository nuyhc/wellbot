"""채팅 영역 상단 GNB (Global Navigation Bar).

좌: 에이전트 모드 드롭다운 | 중앙: 대화 제목 | 우: 다크/라이트 모드 토글
"""

import reflex as rx

from wellbot.state.chat_state import ChatState
from wellbot.styles import COLORS, SPACING


def _agent_mode_item(mode: rx.Var) -> rx.Component:
    """드롭다운 메뉴 아이템."""
    return rx.menu.item(
        rx.hstack(
            rx.icon(mode.icon, size=14),  # type: ignore
            rx.text(mode.name, size="2"),  # type: ignore
            align="center",
            gap="0.5em",
        ),
        on_click=ChatState.set_agent_mode(mode.id),  # type: ignore
    )


def _agent_mode_dropdown() -> rx.Component:
    """에이전트 모드 선택 드롭다운."""
    return rx.menu.root(
        rx.menu.trigger(
            rx.button(
                rx.icon(
                    ChatState.current_agent_mode_icon,
                    size=14,
                ),
                rx.text(
                    ChatState.current_agent_mode_name,
                    size="2",
                    weight="medium",
                ),
                rx.icon("chevron-down", size=12),
                variant="ghost",
                size="1",
                cursor="pointer",
                color=COLORS["text_secondary"],
                _hover={"color": COLORS["text_primary"]},
                gap="0.35em",
            ),
        ),
        rx.menu.content(
            rx.foreach(
                ChatState.agent_mode_list,
                _agent_mode_item,
            ),
            side="bottom",
            align="start",
        ),
    )


def _conversation_title() -> rx.Component:
    """현재 대화 제목 (중앙 정렬)."""
    return rx.text(
        ChatState.current_title,
        size="2",
        weight="medium",
        color=COLORS["text_secondary"],
        text_align="center",
        overflow="hidden",
        text_overflow="ellipsis",
        white_space="nowrap",
        max_width="400px",
    )


def _color_mode_toggle() -> rx.Component:
    """다크/라이트 모드 전환 버튼."""
    return rx.icon_button(
        rx.color_mode_cond(
            light=rx.icon("moon", size=16),
            dark=rx.icon("sun", size=16),
        ),
        variant="ghost",
        size="1",
        cursor="pointer",
        on_click=rx.toggle_color_mode,
        color=COLORS["text_secondary"],
        _hover={"color": COLORS["text_primary"]},
    )


def chat_gnb() -> rx.Component:
    """채팅 영역 GNB."""
    return rx.hstack(
        # 좌: 에이전트 모드
        rx.box(
            _agent_mode_dropdown(),
            flex="1",
            display="flex",
            align_items="center",
        ),
        # 중앙: 대화 제목
        rx.box(
            _conversation_title(),
            flex="1",
            display="flex",
            justify_content="center",
            align_items="center",
        ),
        # 우: 다크/라이트 토글
        rx.box(
            _color_mode_toggle(),
            flex="1",
            display="flex",
            justify_content="flex-end",
            align_items="center",
        ),
        width="100%",
        height=SPACING["gnb_height"],
        padding_x="1em",
        align="center",
        border_bottom=f"1px solid {COLORS['border']}",
        bg=COLORS["main_bg"],
        position="relative",
        z_index="10",
        flex_shrink="0",
    )
