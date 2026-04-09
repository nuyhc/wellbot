"""대화 목록 컴포넌트.

ChatGPT/Gemini 스타일 대화 목록.
활성 대화 하이라이트, 대화 전환, 삭제 기능.
"""

import reflex as rx

from wellbot.state.chat_state import ChatState, Conversation
from wellbot.styles import COLORS, SPACING


def conversation_item(conv: Conversation) -> rx.Component:
    """개별 대화 항목."""
    is_active = ChatState.current_conversation_id == conv.id

    return rx.hstack(
        rx.text(
            conv.title,
            size="2",
            color=rx.cond(is_active, COLORS["text_primary"], COLORS["text_secondary"]),
            weight=rx.cond(is_active, "medium", "regular"),
            overflow="hidden",
            text_overflow="ellipsis",
            white_space="nowrap",
            min_width="0",
            flex="1",
        ),
        rx.icon_button(
            rx.icon("trash-2", size=14),
            variant="ghost",
            size="1",
            cursor="pointer",
            on_click=ChatState.delete_conversation(conv.id),
            opacity="0",
            flex_shrink="0",
            color=COLORS["text_secondary"],
            class_name="delete-btn",
            _hover={"color": rx.color("red", 9)},
        ),
        width="100%",
        max_width="100%",
        padding_x="0.75em",
        padding_y="0.5em",
        align="center",
        spacing="2",
        cursor="pointer",
        border_radius=SPACING["border_radius_sm"],
        bg=rx.cond(is_active, COLORS["sidebar_active"], "transparent"),
        _hover={
            "bg": rx.cond(is_active, COLORS["sidebar_active"], COLORS["sidebar_hover"]),
            "& .delete-btn": {"opacity": "1"},
        },
        on_click=ChatState.switch_conversation(conv.id),
        overflow="hidden",
    )


def conversation_list() -> rx.Component:
    """대화 목록."""
    return rx.box(
        rx.cond(
            ChatState.sorted_conversations.length() > 0,
            rx.vstack(
                # "최근" 카테고리 라벨
                rx.text(
                    "최근",
                    size="1",
                    color=COLORS["category_text"],
                    weight="medium",
                    padding_x="0.75em",
                    padding_top="0.5em",
                    padding_bottom="0.25em",
                ),
                rx.foreach(
                    ChatState.sorted_conversations,
                    conversation_item,
                ),
                spacing="0",
                width="100%",
            ),
            rx.center(
                rx.text(
                    "대화가 없습니다",
                    color=COLORS["text_secondary"],
                    size="2",
                ),
                height="100%",
            ),
        ),
        flex="1",
        overflow_y="auto",
        overflow_x="hidden",
        padding_x="0.5em",
        padding_y="0.25em",
        width="100%",
    )
