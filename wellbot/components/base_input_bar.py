"""메시지 입력 컴포넌트"""
import reflex as rx
from ..state.chat import ChatState


def base_input_bar() -> rx.Component:
    return rx.box(
        rx.form(
            rx.hstack(
                rx.input(
                    value=ChatState.question,
                    placeholder="WellBot에게 질문하세요!",
                    on_change=ChatState.set_question,
                    style={
                        "flex": "1",
                        "background": "transparent",
                        "border": "none",
                        "color": "white",
                        "outline": "none"
                    },
                    id="message_input",
                ),

                rx.button(
                    rx.icon("send", size=18, color="white"),
                    type="submit",
                    loading=ChatState.processing,
                    background="linear-gradient(135deg, #6b21a8, #3b82f6)",
                    border_radius="50%",
                    width="40px",
                    height="40px",
                    padding="0",
                    display="flex",
                    align_items="center",
                    justify_content="center",
                    _hover={
                        "transform": "scale(1.05)",
                        "box_shadow": "0 0 15px rgba(107, 33, 168, 0.5)"
                    },
                    cursor="pointer"
                ),

                width="100%",
                padding="0.5em 0.5em 0.5em 1.5em",
                background="rgba(30, 32, 40, 0.8)",
                border_radius="30px",
                border="1px solid rgba(255, 255, 255, 0.1)",
                box_shadow="0 4px 20px rgba(0, 0, 0, 0.3)",
                align_items="center"
            ),

            on_submit=ChatState.answer,
            reset_on_submit=True,
            width="100%"
        ),
        
        width="100%",
        max_width="1200px",
        margin="0 auto",
        padding="1em 4em 2em 4em"
    )