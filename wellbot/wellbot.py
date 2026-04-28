"""Wellbot 앱 엔트리포인트.

Reflex 앱을 초기화하고 페이지 라우트를 등록한다.
파일 업로드 등 멀티파트 HTTP 엔드포인트는 별도 FastAPI 앱을
`api_transformer` 로 마운트한다.
"""

import reflex as rx

from wellbot.api import api_app
from wellbot.pages.admin import admin
from wellbot.pages.index import index
from wellbot.pages.login import login
from wellbot.pages.register import register
from wellbot.state.admin_state import AdminState
from wellbot.state.auth_state import AuthState
from wellbot.state.chat_state import ChatState
from wellbot.styles import GLOBAL_STYLE, THEME

app = rx.App(
    theme=THEME,
    style=GLOBAL_STYLE,
    api_transformer=api_app,
)
app.add_page(index, route="/", title="WellBot", on_load=[AuthState.check_auth, ChatState.on_load])
app.add_page(login, route="/login", title="WellBot - 로그인", on_load=AuthState.check_login_page)
app.add_page(register, route="/register", title="WellBot - 회원가입", on_load=AuthState.load_dept_list)
app.add_page(admin, route="/admin", title="WellBot - 관리", on_load=AdminState.on_admin_load)
