"""인증 상태 관리 모듈"""
import reflex as rx
import bcrypt
from ..models import User


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


class AuthState(rx.State):
    """인증 관련 상태"""
    # 로그인 폼 필드
    username: str = ""
    password: str = ""
    error_message: str = ""

    # 세션 상태 필드
    current_username: str = ""
    is_authenticated: bool = False
    is_admin: bool = False

    def set_username(self, value: str):
        self.username = value

    def set_password(self, value: str):
        self.password = value

    def clear_form(self):
        self.username = ""
        self.password = ""
        self.error_message = ""

    def login(self):
        self.error_message = ""
        with rx.session() as session:
            user = session.query(User).filter(User.username == self.username).first()
            if user and verify_password(self.password, user.password_hash):
                self.is_authenticated = True
                self.current_username = user.username
                self.is_admin = user.is_admin
                self.clear_form()
                return rx.redirect("/")
            else:
                self.error_message = "아이디 또는 비밀번호가 올바르지 않습니다."

    def logout(self):
        self.is_authenticated = False
        self.current_username = ""
        self.is_admin = False
        self.clear_form()
        return rx.redirect("/login")

    def check_auth(self):
        """인증 여부 확인, 미인증 시 로그인으로 리다이렉트"""
        # TODO: after set Database
        # if not self.is_authenticated:
        #     return rx.redirect("/login")

    def check_admin(self):
        if not self.is_authenticated:
            return rx.redirect("/login")
        if not self.is_admin:
            return rx.redirect("/")