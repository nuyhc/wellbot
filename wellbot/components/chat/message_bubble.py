"""메시지 버블 컴포넌트.

사용자: 우측 정렬, 둥근 배경 버블.
AI: 좌측 정렬, 배경 없이 마크다운 렌더링.
첨부파일은 GNB 팝오버에서 대화 단위로 표시.
"""

import reflex as rx

from wellbot.components.chat.file_icon import file_icon_by_name
from wellbot.state.chat_models import Message
from wellbot.state.chat_state import ChatState
from wellbot.styles import (
    COLORS,
    MARKDOWN_COMPONENT_MAP,
    SPACING,
)


def _source_chip(doc: rx.Var) -> rx.Component:
    """출처 문서 칩 — 클릭 시 presigned URL 다운로드."""
    return rx.el.button(
        file_icon_by_name(doc["title"]),
        rx.text(
            doc["title"],
            size="1",
            color=COLORS["text_secondary"],
            max_width="200px",
            overflow="hidden",
            text_overflow="ellipsis",
            white_space="nowrap",
        ),
        on_click=ChatState.download_kb_source(doc["source_uri"], doc["title"]),
        display="flex",
        align_items="center",
        gap="0.35em",
        background="transparent",
        border=f"1px solid {rx.color('gray', 5)}",
        border_radius=SPACING["border_radius_sm"],
        padding="0.3em 0.65em",
        cursor="pointer",
        _hover={
            "background": str(COLORS["sidebar_hover"]),
            "border_color": str(rx.color("gray", 7)),
        },
    )


def _source_docs_section(message: Message) -> rx.Component:
    """KB 출처 섹션 — AI 메시지 하단."""
    return rx.cond(
        message.source_docs.length() > 0,
        rx.box(
            rx.separator(color=COLORS["border"], size="4"),
            rx.vstack(
                rx.text(
                    "출처",
                    size="1",
                    color=COLORS["text_secondary"],
                    font_weight="500",
                    margin_top="0.6em",
                ),
                rx.flex(
                    rx.foreach(message.source_docs, _source_chip),
                    flex_wrap="wrap",
                    gap="0.4em",
                ),
                gap="0.35em",
                align_items="start",
            ),
            padding_top="0.75em",
            margin_top="0.25em",
        ),
        rx.fragment(),
    )


def user_message(message: Message) -> rx.Component:
    """사용자 메시지 - 우측 정렬, 둥근 버블."""
    return rx.hstack(
        rx.spacer(),
        rx.box(
            rx.text(
                message.content,
                size="3",
                color=COLORS["text_primary"],
                white_space="pre-wrap",
                word_break="break-word",
            ),
            bg=COLORS["user_bubble"],
            padding="0.75em 1.25em",
            border_radius=SPACING["border_radius"],
            max_width="70%",
        ),
        class_name="chat-msg",
        width="100%",
        justify="end",
        padding_x="1em",
    )


def _action_icon(icon: str, on_click: object, tooltip: str = "") -> rx.Component:
    """AI 메시지 하단 액션 아이콘 버튼."""
    return rx.tooltip(
        rx.el.button(
            rx.icon(icon, size=15),
            on_click=on_click,
            background="transparent",
            border="none",
            cursor="pointer",
            color=str(COLORS["text_secondary"]),
            padding="0.3em",
            border_radius="4px",
            display="flex",
            align_items="center",
            _hover={
                "color": str(COLORS["text_primary"]),
                "background": str(COLORS["sidebar_hover"]),
            },
        ),
        content=tooltip,
    )


def _ai_message_actions(message: Message) -> rx.Component:
    """AI 메시지 하단 액션 버튼 바."""
    return rx.hstack(
        _action_icon(
            "copy",
            on_click=rx.set_clipboard(message.content),  # type: ignore
            tooltip="응답 복사",
        ),
        gap="0.25em",
        padding_top="0.25em",
    )


def ai_message(message: Message) -> rx.Component:
    """AI 메시지 - 좌측 정렬, 마크다운 렌더링."""
    return rx.box(
        rx.markdown(
            message.content,
            component_map=MARKDOWN_COMPONENT_MAP,
        ),
        _source_docs_section(message),
        _ai_message_actions(message),
        class_name="chat-msg",
        width="100%",
        color=COLORS["text_primary"],
        padding_x="1em",
    )


def message_bubble(message: Message) -> rx.Component:
    """개별 메시지 - 역할에 따라 분기."""
    return rx.cond(
        message.role == "user",
        user_message(message),
        ai_message(message),
    )
