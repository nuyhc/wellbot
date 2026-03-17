"""메인 채팅 페이지"""
import reflex as rx
from ..state.auth import AuthState
from ..components.sidebar import sidebar
from ..components.chat_area import chat_area
from ..components.base_input_bar import base_input_bar


@rx.page(route="/", on_load=AuthState.check_auth)
def index() -> rx.Component:
    return rx.hstack(
        sidebar(),
        rx.vstack(
            chat_area(),
            base_input_bar(),
            width="100%",
            height="100vh",
            background="#0f111a",
            justify_content="space-between",
            spacing="0"
        ),
        width="100vw",
        height="100vh",
        spacing="0",
        margin="0",
        padding="0",
        background="#0f11a",
        style={"font_family": "Inter, sans-serif"}
    )