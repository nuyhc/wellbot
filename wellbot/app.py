"""WellBot App. Entrypoint"""
import reflex as rx

from .pages.index import index
from .pages.login import login_page
from .pages.admin import admin_page
from .state.admin import AdminState


app = rx.App()
app.add_page(login_page, route="/login", title="Login | WellBot")
app.add_page(admin_page, route="/admin", title="Admin Dashboard | WellBot", on_load=AdminState.load_users)