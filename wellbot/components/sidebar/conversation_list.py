"""대화 목록 컴포넌트.

Sidebar에 대화 목록을 시간 역순으로 표시한다.
활성 대화 하이라이트, 대화 전환, 삭제 기능을 제공한다.
"""

import reflex as rx

from wellbot.state.chat_state import ChatState, Conversation
from wellbot.styles import COLORS


def conversation_item(conv: Conversation) -> rx.Component:
    """개별 대화 항목."""
    is_active = ChatState.current_conversation_id == conv.id

    return rx.hstack(
        rx.icon("message-square", size=14, flex_shrink="0"),
        rx.text(
            conv.title,
            size="2",
            weight=rx.cond(is_active, "medium", "regular"),
            overflow="hidden",
            text_overflow="ellipsis",
            white_space="nowrap",
            min_width="0",
            flex="1",
        ),
        rx.icon_button(
            rx.icon("trash-2", size=12),
            variant="ghost",
            size="1",
            color_scheme="red",
            cursor="pointer",
            on_click=ChatState.delete_conversation(conv.id),
            opacity="0",
            flex_shrink="0",
            _group_hover={"opacity": "1"},
        ),
        width="100%",
        max_width="100%",
        padding_x="0.625em",
        padding_y="0.5em",
        align="center",
        spacing="2",
        cursor="pointer",
        border_radius="0.5em",
        bg=rx.cond(is_active, rx.color("accent", 4), "transparent"),
        color=rx.cond(is_active, rx.color("accent", 11), COLORS["text_primary"]),
        _hover={"bg": rx.cond(is_active, rx.color("accent", 4), rx.color("gray", 3))},
        on_click=ChatState.switch_conversation(conv.id),
        data_group="true",
        overflow="hidden",
    )


def conversation_list() -> rx.Component:
    """대화 목록."""
    return rx.box(
        rx.cond(
            ChatState.sorted_conversations.length() > 0,
            rx.vstack(
                rx.foreach(
                    ChatState.sorted_conversations,
                    conversation_item,
                ),
                spacing="1",
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
        padding_y="0.5em",
        width="100%",
    )
