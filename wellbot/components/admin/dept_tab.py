"""부서 관리 탭 컴포넌트."""

import reflex as rx

from wellbot.components.admin import cell, col_header
from wellbot.state.admin_state import AdminState
from wellbot.styles import COLORS, SPACING


def _dept_row(dept: dict) -> rx.Component:
    """부서 테이블 행."""
    return rx.table.row(
        cell(dept["dept_cd"]),
        cell(dept["dept_nm"]),
        cell(rx.cond(dept["dd_clby_tokn_ecnt"], dept["dd_clby_tokn_ecnt"], "-")),
        cell(rx.cond(dept["mm_clby_tokn_ecnt"], dept["mm_clby_tokn_ecnt"], "-")),
        rx.table.cell(
            rx.hstack(
                rx.icon_button(
                    rx.icon("pencil", size=14),
                    variant="ghost",
                    size="1",
                    cursor="pointer",
                    on_click=AdminState.open_edit_modal("dept", dept),
                ),
                rx.icon_button(
                    rx.icon("trash-2", size=14),
                    variant="ghost",
                    size="1",
                    cursor="pointer",
                    color_scheme="red",
                    on_click=AdminState.delete_dept(dept["dept_cd"]),
                ),
                spacing="1",
                justify="center",
            ),
            text_align="center",
        ),
    )


def dept_modal() -> rx.Component:
    """부서 생성/수정 모달."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.cond(AdminState.is_editing, "부서 수정", "부서 추가"),
            ),
            rx.vstack(
                rx.cond(
                    AdminState.error_message != "",
                    rx.callout(
                        AdminState.error_message,
                        icon="triangle_alert",
                        color_scheme="red",
                        size="1",
                    ),
                ),
                rx.text("부서코드", size="2", weight="medium"),
                rx.input(
                    value=AdminState.form_data.get("dept_cd", ""),
                    placeholder="예: DEPT001",
                    on_change=lambda v: AdminState.set_form_field("dept_cd", v),
                    disabled=AdminState.is_editing,
                    max_length=8,
                ),
                rx.text("부서명", size="2", weight="medium"),
                rx.input(
                    value=AdminState.form_data.get("dept_nm", ""),
                    placeholder="부서명",
                    on_change=lambda v: AdminState.set_form_field("dept_nm", v),
                ),
                rx.text("일별 토큰 수", size="2", weight="medium"),
                rx.input(
                    value=AdminState.form_data.get("dd_clby_tokn_ecnt", ""),
                    placeholder="0",
                    on_change=lambda v: AdminState.set_form_field("dd_clby_tokn_ecnt", v),
                    type="number",
                ),
                rx.text("월별 토큰 수", size="2", weight="medium"),
                rx.input(
                    value=AdminState.form_data.get("mm_clby_tokn_ecnt", ""),
                    placeholder="0",
                    on_change=lambda v: AdminState.set_form_field("mm_clby_tokn_ecnt", v),
                    type="number",
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button("취소", variant="soft", color_scheme="gray"),
                    ),
                    rx.button("저장", on_click=AdminState.save_dept),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),
                spacing="3",
                width="100%",
            ),
        ),
        open=AdminState.show_modal & (AdminState.modal_mode == "dept"),
        on_open_change=lambda open: rx.cond(~open, AdminState.close_modal, None),  # type: ignore
    )


def dept_tab() -> rx.Component:
    """부서 관리 탭."""
    return rx.vstack(
        rx.hstack(
            rx.hstack(
                rx.heading("부서 관리", size="4"),
                rx.text("DEPT_M", size="1", color=COLORS["text_secondary"]),
                align="end",
                spacing="2",
            ),
            rx.spacer(),
            rx.button(
                rx.icon("plus", size=16),
                "부서 추가",
                size="2",
                on_click=AdminState.open_create_modal("dept"),
            ),
            width="100%",
            align="center",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    col_header("부서코드", "DEPT_CD"),
                    col_header("부서명", "DEPT_NM"),
                    col_header("일별 토큰", "DD_CLBY_TOKN_ECNT"),
                    col_header("월별 토큰", "MM_CLBY_TOKN_ECNT"),
                    rx.table.column_header_cell("작업"),
                ),
            ),
            rx.table.body(
                rx.foreach(AdminState.depts, _dept_row),
            ),
            width="100%",
            size="2",
        ),
        rx.cond(
            AdminState.depts.length() == 0,
            rx.center(
                rx.text("등록된 부서가 없습니다.", color=COLORS["text_secondary"], size="2"),
                padding="2em",
            ),
        ),
        dept_modal(),
        spacing="4",
        width="100%",
    )
