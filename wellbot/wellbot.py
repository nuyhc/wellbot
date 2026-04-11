"""Wellbot 앱 엔트리포인트.

Reflex 앱을 초기화하고 페이지 라우트를 등록한다.
"""

import reflex as rx

from wellbot.pages.admin import admin
from wellbot.pages.index import index
from wellbot.pages.login import login
from wellbot.state.admin_state import AdminState
from wellbot.state.chat_state import ChatState
from wellbot.styles import GLOBAL_STYLE, THEME

app = rx.App(
    theme=THEME,
    style=GLOBAL_STYLE,
)
app.add_page(index, route="/", title="Wellbot", on_load=ChatState.on_load)
app.add_page(login, route="/login", title="WellBot - 로그인")
app.add_page(admin, route="/admin", title="WellBot - 관리", on_load=AdminState.on_admin_load)
