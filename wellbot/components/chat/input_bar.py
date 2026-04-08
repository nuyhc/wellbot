"""메시지 입력 바 컴포넌트.

ChatGPT/Gemini 스타일 입력 바.
파일 첨부 버튼 + 텍스트 입력 + 전송 버튼.
"""

import reflex as rx

from wellbot.state.chat_state import ChatState
from wellbot.styles import COLORS, SPACING

# Enter 키 처리를 위한 JavaScript
ENTER_KEY_HANDLER = """
(e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        document.getElementById('send-button').click();
    }
}
"""


def input_bar() -> rx.Component:
    """하단 고정 메시지 입력 바."""
    return rx.box(
        rx.vstack(
            # 입력 컨테이너 (둥근 박스)
            rx.box(
                rx.vstack(
                    # 텍스트 입력 영역
                    rx.el.textarea(
                        placeholder="무엇이든 물어보세요",
                        value=ChatState.current_input,
                        on_change=ChatState.set_input,
                        on_key_down=rx.call_script(ENTER_KEY_HANDLER),
                        rows="1",
                        style={
                            "width": "100%",
                            "resize": "none",
                            "overflow_y": "auto",
                            "max_height": "150px",
                            "min_height": "24px",
                            "padding": "0",
                            "border": "none",
                            "background": "transparent",
                            "color": COLORS["text_primary"],
                            "font_size": "0.9375rem",
                            "line_height": "1.5",
                            "outline": "none",
                            "font_family": "inherit",
                            "::placeholder": {
                                "color": COLORS["text_secondary"],
                            },
                        },
                    ),
                    # 하단: 첨부 버튼 + 전송 버튼
                    rx.hstack(
                        # 파일 첨부 버튼
                        rx.tooltip(
                            rx.icon_button(
                                rx.icon("paperclip", size=16),
                                variant="ghost",
                                size="2",
                                cursor="pointer",
                                color=COLORS["text_secondary"],
                                _hover={
                                    "color": COLORS["text_primary"],
                                    "bg": COLORS["tool_btn_hover"],
                                },
                                border_radius="50%",
                            ),
                            content="파일 첨부",
                        ),
                        rx.spacer(),
                        # 전송 버튼
                        rx.icon_button(
                            rx.icon("arrow-up", size=16),
                            id="send-button",
                            size="2",
                            variant="solid",
                            disabled=~ChatState.can_send,
                            loading=ChatState.is_loading,
                            on_click=[
                                ChatState.send_message,
                                rx.scroll_to("message-bottom"),
                            ],
                            cursor=rx.cond(
                                ChatState.can_send, "pointer", "not-allowed"
                            ),
                            border_radius="50%",
                            bg=rx.cond(
                                ChatState.can_send,
                                COLORS["text_primary"],
                                COLORS["tool_btn_bg"],
                            ),
                            color=rx.cond(
                                ChatState.can_send,
                                COLORS["main_bg"],
                                COLORS["text_secondary"],
                            ),
                            _hover={
                                "bg": rx.cond(
                                    ChatState.can_send,
                                    COLORS["accent_hover"],
                                    COLORS["tool_btn_bg"],
                                ),
                            },
                        ),
                        width="100%",
                        align="center",
                    ),
                    spacing="2",
                    padding="0.75em 1em",
                ),
                bg=COLORS["input_bg"],
                border_radius=SPACING["border_radius"],
                border=f"1px solid {COLORS['input_border']}",
                width="100%",
                max_width=SPACING["message_max_width"],
                margin_x="auto",
                _focus_within={
                    "border_color": COLORS["accent_hover"],
                },
            ),
            # 하단 안내 텍스트
            rx.text(
                "Wellbot은 실수할 수 있습니다. 중요한 정보는 직접 확인하세요.",
                size="1",
                color=COLORS["text_secondary"],
                text_align="center",
            ),
            spacing="2",
            width="100%",
            align="center",
        ),
        width="100%",
        padding_x="1em",
        padding_top="0.75em",
        padding_bottom="1em",
        bg=COLORS["main_bg"],
        flex_shrink="0",
    )
