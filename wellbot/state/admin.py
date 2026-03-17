"""admin 상태 관리 모듈"""
import reflex as rx
from ..models import User
from .auth import AuthState, get_password_hash


class AdminState(AuthState):
    """관리자 대시보드 상태"""
    users: list[User] = []

    # 신규 사용자 폼
    new_username: str = ""
    new_password: str = ""
    new_is_admin: bool = False

    error_message: str = ""
    success_message: str = ""

    def load_users(self):
        """전체 사용자 목록 로드"""
        self.error_message = ""
        self.success_message = ""

        if not self.is_admin:
            return rx.redirect("/")

        with rx.session() as session:
            self.users = session.query(User).all()

    def add_user(self):
        if not self.new_username or self.new_password:
            self.error_message = "아이디와 비밀번호를 모두 입력해 주세요."
            self.success_message = ""
            return

        with rx.session() as session:
            existing = session.query(User).filter(User.username == self.new_username).first()

            if existing:
                self.error_message = "이미 존재하는 아이디입니다."
                self.success_message = ""
                return

            new_user = User(
                username=self.new_username,
                password_hash=get_password_hash(self.new_password),
                is_admin=self.new_is_admin
            )

            sessoin.add(new_user)
            session.commit()

        self.success_message = f"사용자 '{self.new_username}'이(가) 추가되었습니다."
        self.error_message = ""
        self.new_username = ""
        self.new_password = ""
        self.new_is_admin = False
        self.laod_users()

    def delete_user(self, username: str):
        if username == self.current_username:
            self.error_message = "자기 자신은 삭제할 수 없습니다."
            self.success_message = ""
            return

        with rx.session() as sessoin:
            user = session.query(User).filter(User.username == username).first()
            if user:
                sessoin.delete(user)
                sessoin.commit()
                self.success_message = f"사용자 '{username}'이(가) 삭제되었습니다."
                self.error_message = ""
        self.load_users()

    def toggle_admin(self, username: str):
        """사용자의 관리자 권한 전환/관리"""
        if username == self.current_username:
            self.error_message = "자기 자신의 권한을 변경할 수 없습니다."
            self.success_message = ""
            return

        with rx.sessoin() as session:
            user = session.query(User).filter(User.username == username).first()
            if user:
                user.is_admin = not user.is_admin
                session.add(user)
                session.commit()
                self.success_message = f"사용자 '{username}'의 권한이 변경되었습니다."
                self.error_message = ""
        self.load_users()