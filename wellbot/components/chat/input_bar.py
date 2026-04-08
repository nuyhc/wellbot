"""메시지 입력 바 컴포넌트.

텍스트 입력, Enter 전송, Shift+Enter 줄바꿈, 빈 입력 시 전송 버튼 비활성화.
"""

import reflex as rx

from wellbot.state.chat_state import ChatState
from wellbot.styles import COLORS, SPACING

# Enter 키 처리를 위한 JavaScript
# Shift+Enter: 줄바꿈 (기본 동작 유지)
# Enter: 전송 (기본 동작 방지 후 이벤트 발생)
ENTER_KEY_HANDLER = """
(e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        // Reflex 이벤트 트리거
        document.getElementById('send-button').click();
    }
}
"""


def input_bar() -> rx.Component:
    """하단 고정 메시지 입력 바."""
    return rx.box(
        rx.hstack(
            rx.el.textarea(
                placeholder="메시지를 입력하세요...",
                value=ChatState.current_input,
                on_change=ChatState.set_input,
                on_key_down=rx.call_script(ENTER_KEY_HANDLER),
                rows="1",
                style={
                    "width": "100%",
                    "resize": "none",
                    "overflow_y": "auto",
                    "max_height": "120px",
                    "min_height": "40px",
                    "padding": "0.625em 1em",
                    "border_radius": SPACING["border_radius"],
                    "border": f"1px solid {COLORS['input_border']}",
                    "background": str(COLORS["input_bg"]),
                    "color": str(COLORS["text_primary"]),
                    "font_size": "0.9375rem",
                    "line_height": "1.5",
                    "outline": "none",
                    "font_family": "inherit",
                    "&:focus": {
                        "border_color": str(COLORS["accent"]),
                    },
                },
            ),
            rx.icon_button(
                rx.icon("send", size=18),
                id="send-button",
                size="3",
                variant="solid",
                disabled=~ChatState.can_send,
                loading=ChatState.is_loading,
                on_click=[
                    ChatState.send_message,
                    rx.scroll_to("message-bottom"),
                ],
                cursor=rx.cond(ChatState.can_send, "pointer", "not-allowed"),
                border_radius=SPACING["border_radius"],
            ),
            width="100%",
            max_width=SPACING["message_max_width"],
            margin_x="auto",
            align="end",
            spacing="3",
        ),
        position="fixed",
        bottom="0",
        left="0",
        right="0",
        padding="1em",
        padding_bottom="1.5em",
        bg=COLORS["main_bg"],
        border_top=f"1px solid {COLORS['border']}",
        z_index="5",
    )
