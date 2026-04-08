"""로그인 페이지.

이메일/비밀번호 입력 폼과 인증 처리를 담당한다.
Phase 4에서 실제 인증 로직 구현 예정.
"""

import reflex as rx

from wellbot.styles import COLORS


def login() -> rx.Component:
    """로그인 페이지."""
    return rx.box(
        rx.center(
            rx.vstack(
                rx.icon("lock", size=48, color=COLORS["accent"]),
                rx.heading("로그인", size="6"),
                rx.text(
                    "Phase 4에서 인증 기능이 구현됩니다.",
                    color=COLORS["text_secondary"],
                    size="2",
                ),
                align="center",
                spacing="3",
            ),
            height="100vh",
        ),
        bg=COLORS["main_bg"],
    )
