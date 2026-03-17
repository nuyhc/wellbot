"""채팅 영역 컴포넌트"""
import reflex as rx
from ..state.chat import ChatState


def message(qa: tuple[str, str]) -> rx.Component:
    """단일 질문/답변 메시지 버블"""
    return rx.box(
        # User
        rx.box(
            rx.text(qa[0], style={"color": "white", "font_size": "0.95em"}),
            background="linear-gradient(135deg, #6b21a8, #3b82f6)",
            padding="1em 1.2em",
            border_radius="18px 18px 4px, 18px",
            margin_bottom="1.5em",
            align_self="felx-end",
            display="inline-block",
            max_width="75%",
            box_shadow="0 4px 15px rgba(107, 33, 168, 0.2)"
        ),
        # Assistant
        rx.cond(
            qa[1] != "",
            rx.box(
                rx.markdown(qa[1]),
                color="white",
                background="rgba(30, 32, 40, 0.8)",
                padding="1em 1.2em",
                border_radius="18px 18px 18px 4px",
                margin_bottom="1.5em",
                align_self="flex-start",
                display="inline-block",
                max_width="85%",
                border="1px solid rgba(255, 255, 255, 0.05)",
                box_shadow="0 4px 15px rgba(0, 0, 0, 0.2)"
            )
        ),
        display="flex",
        flex_direction="column",
        width="100%"
    )


def thinking_indicator() -> rx.Component:
    """모델 응답 생성 중 표시 인디케이터"""
    return rx.cond(
        ChatState.processing,
        rx.box(
            rx.hstack(
                rx.spinner(size="2", color="#a855f7"),
                rx.vstack(
                    rx.text(ChatState.selected_model, size="1", color="#a855f7", weight="bold"),
                    rx.text("Thinking...", size="2", color="gray"),
                    spacing="0"
                ),
                spacing="2",
                align_items="center"
            ),

            background="rgba(30, 32, 40, 0.8)",
            padding="0.8em 1.2em",
            border_radius="18px 18px 18px 4px",
            margin_bottom="1.5em",
            align_self="flex-start",
            display="inline-block",
            border="1px solid rgba(168, 85, 247, 0.2)",
            animation="pulse 2s ease-in-out infinite"
        )
    )


def chat_area() -> rx.Component:
    """메인 채팅 영역"""
    return rx.box(
        rx.foreach(ChatState.chat_history, message),

        thinking_indicator(),
        
        padding="2em 4em",
        width="100%",
        max_width="1200px",
        margin="0 auto",
        flex="1",
        overflow_y="auto"
    )