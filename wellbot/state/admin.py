"""admin 상태 관리 모듈"""
import reflex as rx
from datetime import datetime
from wellbot.models import EmpM
from wellbot.state.auth import AuthState, get_password_hash


class AdminState(AuthState):
    """관리자 대시보드 상태"""
    users: list[EmpM] = []

    # 신규 사용자 폼
    new_emp_no: str = ""
    new_user_nm: str = ""
    new_password: str = ""
    new_role: str = "user"

    error_message: str = ""
    success_message: str = ""

    def set_new_emp_no(self, value: str):
        self.new_emp_no = value

    def set_new_user_nm(self, value: str):
        self.new_user_nm = value

    def set_new_password(self, value: str):
        self.new_password = value

    def set_new_role(self, value: str):
        self.new_role = value

    def load_users(self):
        """전체 사용자 목록 로드"""
        self.error_message = ""
        self.success_message = ""

        if not self.is_admin:
            return rx.redirect("/")

        with rx.session() as session:
            self.users = session.query(EmpM).all()

    def add_user(self):
        if not self.new_emp_no or not self.new_password:
            self.error_message = "사원번호와 비밀번호를 모두 입력해 주세요."
            self.success_message = ""
            return

        now = datetime.now()
        with rx.session() as session:
            existing = session.query(EmpM).filter(
                EmpM.emp_no == self.new_emp_no
            ).first()

            if existing:
                self.error_message = "이미 존재하는 사원번호입니다."
                self.success_message = ""
                return

            new_emp = EmpM(
                emp_no=self.new_emp_no,
                user_nm=self.new_user_nm or self.new_emp_no,
                ecr_pwd=get_password_hash(self.new_password),
                user_role_nm=self.new_role,
                pstn_dept_cd="1",
                acnt_sts_nm="active",
                rgst_dtm=now,
                rgsr_id=self.current_emp_no or "SYSTEM",
                upd_dtm=now,
                uppr_id=self.current_emp_no or "SYSTEM",
            )

            session.add(new_emp)
            session.commit()

        self.success_message = f"사용자 '{self.new_emp_no}'이(가) 추가되었습니다."
        self.error_message = ""
        self.new_emp_no = ""
        self.new_user_nm = ""
        self.new_password = ""
        self.new_role = "user"
        self.load_users()

    def delete_user(self, emp_no: str):
        if emp_no == self.current_emp_no:
            self.error_message = "자기 자신은 삭제할 수 없습니다."
            self.success_message = ""
            return

        with rx.session() as session:
            emp = session.query(EmpM).filter(EmpM.emp_no == emp_no).first()
            if emp:
                session.delete(emp)
                session.commit()
                self.success_message = f"사용자 '{emp_no}'이(가) 삭제되었습니다."
                self.error_message = ""
        self.load_users()

    def toggle_admin(self, emp_no: str):
        """사용자의 관리자 권한 전환"""
        if emp_no == self.current_emp_no:
            self.error_message = "자기 자신의 권한을 변경할 수 없습니다."
            self.success_message = ""
            return

        with rx.session() as session:
            emp = session.query(EmpM).filter(EmpM.emp_no == emp_no).first()
            if emp:
                if emp.user_role_nm == "admin":
                    emp.user_role_nm = "user"
                else:
                    emp.user_role_nm = "admin"
                session.add(emp)
                session.commit()
                self.success_message = f"사용자 '{emp_no}'의 권한이 변경되었습니다."
                self.error_message = ""
        self.load_users()
