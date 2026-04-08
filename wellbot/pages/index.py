"""채팅 메인 페이지.

2단 레이아웃(Sidebar + 메시지 영역 + 입력 바)을 조립한다.
"""

import reflex as rx

from wellbot.components.chat.input_bar import input_bar
from wellbot.components.chat.message_area import message_area
from wellbot.components.layout import chat_layout
from wellbot.state.chat_state import ChatState


def chat_main() -> rx.Component:
    """메인 대화 영역: 메시지 표시 + 입력 바."""
    return rx.vstack(
        message_area(),
        input_bar(),
        height="100%",
        width="100%",
        spacing="0",
        position="relative",
    )


def index() -> rx.Component:
    """채팅 메인 페이지."""
    return chat_layout(chat_main())
