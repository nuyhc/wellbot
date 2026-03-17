"""WellBot App. Entrypoint"""
import reflex as rx

from wellbot.pages.index import index
from wellbot.pages.login import login_page
from wellbot.pages.admin import admin_page
from wellbot.state.admin import AdminState


app = rx.App()
app.add_page(login_page, route="/login", title="Login | WellBot")
app.add_page(admin_page, route="/admin", title="Admin Dashboard | WellBot", on_load=AdminState.load_users)