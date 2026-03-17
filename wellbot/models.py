import reflex as rx


class User(rx.Model, table=True):
    __tablename__ = "wellbot_user"
    username: str
    password_hash: str
    is_admin: bool = False