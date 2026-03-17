"""로그인 페이지"""
import reflex as rx
from wellbot.state.auth import AuthState


def login_page() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("WellBot💡", size="8", color="white", margin_bottom="0.5em"),
            rx.text("가입된 정보를 로그인해주세요.", color="gray", margin_bottom="2em"),

            rx.cond(
                AuthState.error_message != "",
                rx.text(AuthState.error_message, color="red", margin_bottom="1em")
            ),

            rx.form(
                rx.vstack(
                    rx.vstack(
                        rx.text("아이디", color="gray", size="2", font_weight="bold"),
                        rx.input(
                            placeholder="Enter Username",
                            valude=AuthState.username,
                            on_change=AuthState.set_username,
                            background="rgba(30, 32, 40, 0.8)",
                            border="1px solid rgba(255, 255, 255, 0.1)",
                            color="white",
                            size="3",
                            border_radius="8px",
                            width="100%"
                        ),
                        
                        align_items="start",
                        width="100%",
                        margin_bottom="1.5em"
                    ),

                    rx.vstack(
                        rx.text("비밀번호", color="gray", size="2", font_weight="bold"),
                        rx.input(
                            placeholder="Enter Password",
                            type="password",
                            value=AuthState.password,
                            on_change=AuthState.set_password,
                            background="rgba(30, 32, 40, 0.8)",
                            border="1px solid rgba(255, 255, 255, 0.1)",
                            color="white",
                            size="3",
                            border_radius="8px",
                            width="100%"
                        ),

                        align_items="start",
                        width="100%",
                        margin_bottom="2em"
                    ),

                    rx.button(
                        "로그인",
                        type="submit",
                        width="100%",
                        background="linear-gradient(135deg, #6b21a8, #3b82f6)",
                        color="white",
                        padding="1em",
                        border_radius="8px",
                        font_weight="bold",
                        _hover={
                            "transform": "scale(1.02)",
                            "box_shadow": "0 0 15px rgba(107, 33, 168, 0.5)"
                        }
                    ),
                    width="100%"
                ),
                on_submit=AuthState.login,
                width="100%"
            ),

            width="100%",
            max_width="400px",
            background="rgba(20, 22, 30, 0.7)",
            padding="3em",
            border_radius="16px",
            box_shadow="0 8px 30px rgba(0, 0, 0, 0.5)",
            backdrop_filter="blur(10px)",
            border="1px solid rgba(255, 255, 255, 0.05)",
            align_items="center"
        ),

        width="100vw",
        height="100vh",
        background="#0f111a",
        style={"font_family": "Inter, sans-serif"}
    )
