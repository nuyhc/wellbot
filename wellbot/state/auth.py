"""인증 상태 관리 모듈"""
import reflex as rx
import bcrypt
from wellbot.models import EmpM


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
    current_emp_no: str = ""
    current_user_nm: str = ""
    is_authenticated: bool = False
    user_role: str = ""

    @rx.var
    def is_admin(self) -> bool:
        return self.user_role in ("super-admin", "admin")

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
            emp = session.query(EmpM).filter(EmpM.emp_no == self.username).first()
            if emp and emp.ecr_pwd and verify_password(self.password, emp.ecr_pwd):
                if emp.acnt_sts_nm != "active":
                    self.error_message = "비활성화된 계정입니다."
                    return
                self.is_authenticated = True
                self.current_emp_no = emp.emp_no
                self.current_user_nm = emp.user_nm or emp.emp_no
                self.user_role = emp.user_role_nm
                self.clear_form()
                return rx.redirect("/")
            else:
                self.error_message = "아이디 또는 비밀번호가 올바르지 않습니다."

    def logout(self):
        self.is_authenticated = False
        self.current_emp_no = ""
        self.current_user_nm = ""
        self.user_role = ""
        self.clear_form()
        return rx.redirect("/login")

    def check_auth(self):
        """인증 여부 확인, 미인증 시 로그인으로 리다이렉트"""
        # TODO: after set Database
        # if not self.is_authenticated:
        #     return rx.redirect("/login")
        pass

    def check_admin(self):
        if not self.is_authenticated:
            return rx.redirect("/login")
        if not self.is_admin:
            return rx.redirect("/")
