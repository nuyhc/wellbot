"""메시지 버블 컴포넌트.

ChatGPT/Gemini 스타일 메시지 표시.
사용자: 우측 정렬, 둥근 배경 버블.
AI: 좌측 정렬, 배경 없이 마크다운 렌더링.
사용자 메시지에 첨부파일이 있으면 버블 하단에 카드 목록을 표시.
"""

import reflex as rx

from wellbot.state.chat_state import AttachmentInfo, ChatState, Message
from wellbot.styles import COLORS, MARKDOWN_COMPONENT_MAP, SPACING


def _format_token_label(tokens: int, mime: str) -> str:
    """토큰 수 라벨. 이미지 여부는 MIME 으로 판별."""
    return rx.cond(
        tokens > 0,
        f"{tokens} 토큰",
        rx.cond(
            mime.contains("image"),
            "이미지",
            "문서",
        ),
    )


def _attachment_icon(mime: str) -> rx.Component:
    """MIME 별 아이콘."""
    return rx.cond(
        mime.contains("image"),
        rx.icon("image", size=18, color=COLORS["text_secondary"]),
        rx.cond(
            mime.contains("pdf"),
            rx.icon("file-text", size=18, color=COLORS["text_secondary"]),
            rx.cond(
                mime.contains("spreadsheet"),
                rx.icon("table-2", size=18, color=COLORS["text_secondary"]),
                rx.cond(
                    mime.contains("presentation"),
                    rx.icon("presentation", size=18, color=COLORS["text_secondary"]),
                    rx.cond(
                        mime.contains("word") | mime.contains("hwp"),
                        rx.icon("file-pen-line", size=18, color=COLORS["text_secondary"]),
                        rx.cond(
                            mime.contains("markdown"),
                            rx.icon("file-code", size=18, color=COLORS["text_secondary"]),
                            rx.cond(
                                mime.contains("text/plain"),
                                rx.icon("file-type", size=18, color=COLORS["text_secondary"]),
                                rx.icon("file", size=18, color=COLORS["text_secondary"]),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def _attachment_card(att: AttachmentInfo) -> rx.Component:
    """단일 첨부 카드 - 클릭 시 다운로드."""
    return rx.hstack(
        _attachment_icon(att.mime),
        rx.vstack(
            rx.text(
                att.name,
                size="2",
                weight="medium",
                color=COLORS["text_primary"],
                max_width="220px",
                overflow="hidden",
                text_overflow="ellipsis",
                white_space="nowrap",
            ),
            rx.hstack(
                rx.cond(
                    att.token_count > 0,
                    rx.text(
                        f"{att.token_count} 토큰",
                        size="1",
                        color=COLORS["text_secondary"],
                    ),
                    rx.cond(
                        att.status == "processing",
                        rx.hstack(
                            rx.spinner(size="1"),
                            rx.text(
                                "처리 중",
                                size="1",
                                color=COLORS["text_secondary"],
                            ),
                            gap="0.3em",
                            align="center",
                        ),
                        rx.text(
                            rx.cond(
                                att.mime.contains("image"),
                                "이미지",
                                "문서",
                            ),
                            size="1",
                            color=COLORS["text_secondary"],
                        ),
                    ),
                ),
                gap="0.3em",
                align="center",
            ),
            spacing="0",
            align="start",
        ),
        rx.spacer(),
        rx.icon(
            "download",
            size=16,
            color=COLORS["text_secondary"],
        ),
        align="center",
        gap="0.5em",
        padding="0.5em 0.75em",
        border=f"1px solid {COLORS['border']}",
        border_radius=SPACING["border_radius_sm"],
        bg=COLORS["input_bg"],
        cursor="pointer",
        _hover={"bg": COLORS["sidebar_hover"]},
        on_click=ChatState.download_attachment(att.file_no),
        min_width="240px",
    )


def _attachments_section(message: Message) -> rx.Component:
    """메시지 하단의 첨부 카드 그리드."""
    return rx.cond(
        message.attachments,
        rx.hstack(
            rx.foreach(message.attachments, _attachment_card),
            gap="0.5em",
            flex_wrap="wrap",
            padding_top="0.5em",
            justify="end",
            width="100%",
        ),
    )


def user_message(message: Message) -> rx.Component:
    """사용자 메시지 - 우측 정렬, 둥근 버블. 첨부 있으면 버블 아래에 카드."""
    return rx.vstack(
        rx.hstack(
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
            width="100%",
            justify="end",
        ),
        _attachments_section(message),
        width="100%",
        padding_x="1em",
        align="end",
        spacing="1",
    )


def ai_message(message: Message) -> rx.Component:
    """AI 메시지 - 좌측 정렬, 마크다운 렌더링."""
    return rx.box(
        rx.markdown(
            message.content,
            component_map=MARKDOWN_COMPONENT_MAP,
        ),
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
