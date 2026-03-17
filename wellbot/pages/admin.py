"""관리자 대시보드 페이지"""
import reflex as rx
from ..models import User
from ..state.admin import AdminState


def user_row(user: User) -> rx.Component:
    """사용자 테이블"""
    return rx.table.row(
        rx.table.cell(rx.text(user.username, color="white")),

        rx.table.cell(
            rx.cond(
                user.is_admin,
                rx.badge("Admin", color_scheme="purple", variant="solid"),
                rx.badge("User", color_scheme="gray", variant="solid")
            )
        ),

        rx.table.cell(
            rx.hstack(
                rx.button(
                    "권한 토글",
                    size="1",
                    on_click=lambda: AdminState.toggle_admin(user.username),
                    variant="outline",
                    color_scheme="purple"
                ),

                rx.button(
                    "삭제",
                    size="1",
                    on_click=lambda: AdminState.delete_user(user.username),
                    variant="solid",
                    color_scheme="red"
                )
            )
        )
    )


def admin_page() -> rx.Component:
    """관리자 대시보드 페이지"""
    return rx.box(
        rx.hstack(
            rx.heading("관리자 대시보드", size="6", color="white"),
            rx.spacer(),
            rx.button("back", on_click=rx.redirect("/"), variant="outline"),
            width="100%",
            padding="2em",
            border_bottom="1px solid rgba(255, 255, 255, 0.1)"
        ),

        rx.vstack(
            # 알림 메시지
            rx.cond(
                AdminState.error_message != "",
                rx.text(AdminState.error_message, color="red")
            ),
            rx.cond(
                AdminState.success_message != "",
                rx.text(AdminState.success_message, color="green")
            ),

            # 사용자 추가
            rx.box(
                rx.heading("Add User", size="4", color="white", margin_bottom="1em"),
                rx.hstack(
                    rx.input(
                        placeholder="Username",
                        value=AdminState.new_username,
                        on_change=AdminState.set_new_username
                    ),
                    rx.input(
                        placeholder="Password",
                        type="password",
                        value=AdminState.new_password,
                        on_change=AdminState.set_new_password
                    ),
                    rx.checkbox(
                        "Admin 권한 부여",
                        checked=AdminState.new_is_admin,
                        on_change=AdminState.set_new_is_admin,
                        color="white"
                    ),
                    rx.button("사용자 생성", on_click=AdminState.add_user, color_scheme="blue"),
                    align_items="center"
                ),

                padding="1.5em",
                background="rgba(30, 32, 40, 0.5)",
                border_radius="10px",
                width="100%",
                margin_bottom="2em"
            ),

            # 사용자 테이블
            rx.box(
                rx.heading("전체 사용자 목록", size="4", color="white", margin_bottom="1em"),
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("아이디", color="gray"),
                            rx.table.column_header_cell("권한", color="gray"),
                            rx.table.column_header_cell("액션", color="gray")
                        )
                    ),
                    
                    rx.table.body(rx.foreach(AdminState.users, user_row)),
                    variant="surface",
                    color_scheme="gray"
                ),
                width="100%"
            ),

            padding="2em",
            width="100%",
            max_width="1000px",
            margin="0 auth"
        ),

        width="100vw",
        min_height="100vh",
        background="#0f111a",
        style={"font_family": "Inter, sans-serif"}
    )