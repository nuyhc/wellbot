"""에이전트 관리 탭 컴포넌트."""

import reflex as rx

from wellbot.components.admin import cell, col_header
from wellbot.state.admin_state import AdminState
from wellbot.styles import COLORS


def _agent_row(agent: dict) -> rx.Component:
    """에이전트 테이블 행."""
    key = rx.Var.create(f'{agent["agnt_id"]}|{agent["agnt_seq"]}')
    return rx.table.row(
        cell(agent["agnt_id"]),
        cell(agent["agnt_seq"]),
        cell(agent["agnt_nm"]),
        cell(agent["agnt_frwk_nm"]),
        cell(
            rx.badge(
                agent["use_yn"],
                size="1",
                variant="soft",
                color_scheme=rx.cond(agent["use_yn"] == "Y", "green", "gray"),
            ),
        ),
        rx.table.cell(
            rx.hstack(
                rx.icon_button(
                    rx.icon("pencil", size=14),
                    variant="ghost",
                    size="1",
                    cursor="pointer",
                    on_click=AdminState.open_edit_modal("agent", agent),
                ),
                rx.icon_button(
                    rx.icon("trash-2", size=14),
                    variant="ghost",
                    size="1",
                    cursor="pointer",
                    color_scheme="red",
                    on_click=AdminState.delete_agent(key),
                ),
                spacing="1",
                justify="center",
            ),
            text_align="center",
        ),
    )


def agent_modal() -> rx.Component:
    """에이전트 생성/수정 모달."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                rx.cond(AdminState.is_editing, "에이전트 수정", "에이전트 추가"),
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
                rx.text("에이전트 ID", size="2", weight="medium"),
                rx.input(
                    value=AdminState.form_data.get("agnt_id", ""),
                    placeholder="예: AgntReport",  # 별도 관리 엑셀 필요
                    on_change=lambda v: AdminState.set_form_field("agnt_id", v),
                    disabled=AdminState.is_editing,
                    max_length=50,
                ),
                rx.text("순번", size="2", weight="medium"),
                rx.input(
                    value=AdminState.form_data.get("agnt_seq", "1"),
                    placeholder="1",
                    on_change=lambda v: AdminState.set_form_field("agnt_seq", v),
                    type="number",
                    disabled=AdminState.is_editing,
                ),
                rx.text("에이전트명", size="2", weight="medium"),
                rx.input(
                    value=AdminState.form_data.get("agnt_nm", ""),
                    placeholder="에이전트명",
                    on_change=lambda v: AdminState.set_form_field("agnt_nm", v),
                ),
                rx.text("프레임워크", size="2", weight="medium"),
                rx.input(
                    value=AdminState.form_data.get("agnt_frwk_nm", ""),
                    placeholder="예: LangGraph, CrewAI",
                    on_change=lambda v: AdminState.set_form_field("agnt_frwk_nm", v),
                ),
                rx.text("경로", size="2", weight="medium"),
                rx.input(
                    value=AdminState.form_data.get("agnt_path_addr", ""),
                    placeholder="/path/to/agent",
                    on_change=lambda v: AdminState.set_form_field("agnt_path_addr", v),
                ),
                rx.text("설명", size="2", weight="medium"),
                rx.text_area(
                    value=AdminState.form_data.get("agnt_dscr_cntt", ""),
                    placeholder="에이전트 설명",
                    on_change=lambda v: AdminState.set_form_field("agnt_dscr_cntt", v),
                    rows="3",
                ),
                rx.text("사용 여부", size="2", weight="medium"),
                rx.select(
                    ["Y", "N"],
                    value=AdminState.form_data.get("use_yn", "Y"),
                    on_change=lambda v: AdminState.set_form_field("use_yn", v),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button("취소", variant="soft", color_scheme="gray"),
                    ),
                    rx.button("저장", on_click=AdminState.save_agent),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),
                spacing="3",
                width="100%",
            ),
            max_width="520px",
        ),
        open=AdminState.show_modal & (AdminState.modal_mode == "agent"),
        on_open_change=lambda open: rx.cond(~open, AdminState.close_modal, None),  # type: ignore
    )


def agent_tab() -> rx.Component:
    """에이전트 관리 탭."""
    return rx.vstack(
        rx.hstack(
            rx.hstack(
                rx.heading("에이전트 관리", size="4"),
                rx.text("AGNT_M", size="1", color=COLORS["text_secondary"]),
                align="end",
                spacing="2",
            ),
            rx.spacer(),
            rx.button(
                rx.icon("plus", size=16),
                "에이전트 추가",
                size="2",
                on_click=AdminState.open_create_modal("agent"),
            ),
            width="100%",
            align="center",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    col_header("ID", "AGNT_ID"),
                    col_header("순번", "AGNT_SEQ"),
                    col_header("에이전트명", "AGNT_NM"),
                    col_header("프레임워크", "AGNT_FRWK_NM"),
                    col_header("사용", "USE_YN"),
                    rx.table.column_header_cell("작업"),
                ),
            ),
            rx.table.body(
                rx.foreach(AdminState.agents, _agent_row),
            ),
            width="100%",
            size="2",
        ),
        rx.cond(
            AdminState.agents.length() == 0,
            rx.center(
                rx.text("등록된 에이전트가 없습니다.", color=COLORS["text_secondary"], size="2"),
                padding="2em",
            ),
        ),
        agent_modal(),
        spacing="4",
        width="100%",
    )
