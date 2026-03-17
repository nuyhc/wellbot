"""사이드바 컴포넌트"""
import reflex as rx
from wellbot.state.auth import AuthState
from wellbot.state.chat import ChatState, MODEL_NAMES


def sidebar() -> rx.Component:
    return rx.vstack(
        # 로고
        rx.hstack(
            rx.icon("message-square", color="#a855f7", size=28),
            rx.heading("WellBot", size="6", color="white", weight="bold"),
            align_items="center",
            margin_bottom="2em"
        ),

        # 유저 정보
        rx.hstack(
            rx.icon("user", color="gray"),
            rx.text(AuthState.current_username, color="white", weight="bold"),
            align_items="center",
            margin_bottom="1em"
        ),

        # 모델 선택 드롭다운
        rx.vstack(
            rx.text("Selected Model", size="2", color="gray", weight="bold", margin_bottom="0.3em"),
            rx.select(
                MODEL_NAMES,
                value=ChatState.selected_model,
                on_change=ChatState.set_selected_model,
                width="100%",
                size="2"
            ),
            width="100%",
            margin_bottom="1em"
        ),

        # TODO: New Chat
        rx.button(
            rx.icon("plus", size=10),
            rx.text("New Chat"),
            width="100%",
            background="linear-gradient(135deg, rgba(107, 33, 168, 0.2), rgba(59, 130, 246, 0.2))",
            color="white",
            border="1px solid rgba(168, 85, 247, 0.3)",
            border_radius="8px",
            justify_content="flex-start",
            padding="1em",
            _hover={
                "background": "linear-gradient(135deg, rgba(107, 33, 168, 0.4), rgba(59, 130, 246, 0.4))",
                "box_shadow": "0 0 10px rgba(107, 33, 168, 0.3)"
            }
        ),

        rx.spacer(),

        # TODO: Chat History
        rx.vstack(
            rx.text("History", size="2", color="gray", weight="bold", margin_bottom="0.5em"),
            rx.text("Previous conversations will appear here.", size="1", color="gray"),
            widht="100%",
            padding_top="2em",
            border_top="1px solid rgba(255, 255, 255, 0.05)",
        ),

        # 하단 컨트롤 (Admin / Logout)
        rx.vstack(
            rx.cond(
                AuthState.is_admin,
                rx.button(
                    rx.icon("shield", size=14),
                    rx.text("Admin Dashboard"),
                    on_click=rx.redirect("/admin"),
                    width="100%",
                    variant="soft",
                    color_scheme="purple",
                    margin_bottom="0.5em"
                )
            ),

            rx.button(
                rx.icon("log-out", size=14),
                rx.text("Logout"),
                on_click=AuthState.logout,
                width="100%",
                variant="outline",
                color_scheme="red"
            ),
            width="100%",
            margin_top="1em"
        ),

        width="260px",
        height="100vh",
        background="rgba(20, 22, 30, 0.7)",
        backdrop_filter="blur(16px)",
        border_right="1px solid rgba(255, 255, 255, 0.05)",
        padding="1.5em",
        align_items="flex-start"
    )