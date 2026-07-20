"""보고서 문구 작성 지원 페이지.

chat_layout 으로 래핑(표준 wellbot 사이드바 유지)하고, 메인 영역에 보고서 유형 선택
→ 대화(생성 흐름) UI 를 렌더한다. 업로드는 커스텀 API(fetch) 로 처리한다.
"""

import reflex as rx

from wellbot.components.layout import chat_layout
from wellbot.state.report_maker_scripts import REPORT_MAKER_SCRIPT
from wellbot.state.report_maker_state import ReportMakerState, ReportMessage
from wellbot.styles import COLORS, SPACING

_ACCENT = "#E97055"


def _template_menu() -> rx.Component:
    """보고서 유형 선택/생성 드롭다운."""
    return rx.box(
        rx.button(
            rx.icon("layout-template", size=16),
            ReportMakerState.template_display,
            rx.icon("chevron-down", size=14),
            on_click=ReportMakerState.toggle_template_menu,
            variant="soft",
            color_scheme="gray",
            size="2",
        ),
        rx.cond(
            ReportMakerState.show_template_menu,
            rx.fragment(
                rx.box(
                    on_click=ReportMakerState.close_template_menu,
                    position="fixed",
                    inset="0",
                    z_index="40",
                ),
                rx.vstack(
                    rx.foreach(
                        ReportMakerState.templates,
                        lambda t: rx.hstack(
                            rx.text(
                                t["display"],
                                size="2",
                                color=COLORS["text_primary"],
                                cursor="pointer",
                                flex="1",
                                on_click=ReportMakerState.select_template(t["id"]),
                            ),
                            rx.icon(
                                "trash-2",
                                size=14,
                                color=COLORS["text_secondary"],
                                cursor="pointer",
                                on_click=ReportMakerState.delete_template(t["id"]),
                            ),
                            width="100%",
                            align="center",
                            padding="0.4em 0.6em",
                            _hover={"background": COLORS["sidebar_hover"]},
                            border_radius=SPACING["border_radius_sm"],
                        ),
                    ),
                    rx.divider(),
                    rx.form(
                        rx.hstack(
                            rx.input(
                                name="template_name",
                                placeholder="새 보고서 유형명 (예: 먼슬리)",
                                size="2",
                                flex="1",
                            ),
                            rx.button("추가", type="submit", size="2", color_scheme="gray"),
                            width="100%",
                        ),
                        on_submit=ReportMakerState.create_template,
                        reset_on_submit=True,
                        width="100%",
                    ),
                    position="absolute",
                    top="110%",
                    left="0",
                    z_index="50",
                    width="320px",
                    padding="0.5em",
                    bg=COLORS["sidebar_bg"],
                    border=f"1px solid {COLORS['border']}",
                    border_radius=SPACING["border_radius_md"],
                    box_shadow="0 8px 24px rgba(0,0,0,0.15)",
                    spacing="1",
                ),
            ),
        ),
        position="relative",
    )


def _setup_view() -> rx.Component:
    """세션 시작 전 — 보고서 유형 선택/생성."""
    return rx.center(
        rx.vstack(
            rx.icon("sparkles", size=32, color=_ACCENT),
            rx.heading("보고서 문구 작성 지원", size="6", color=COLORS["text_primary"]),
            rx.text(
                "보고서 유형을 선택하거나 새로 만들어 시작하세요.",
                size="2",
                color=COLORS["text_secondary"],
            ),
            rx.cond(
                ReportMakerState.has_templates,
                rx.vstack(
                    rx.foreach(
                        ReportMakerState.templates,
                        lambda t: rx.button(
                            t["display"],
                            on_click=ReportMakerState.select_template(t["id"]),
                            variant="soft",
                            color_scheme="gray",
                            width="100%",
                            justify="start",
                        ),
                    ),
                    width="100%",
                    spacing="2",
                ),
                rx.text("아직 만든 보고서 유형이 없습니다.", size="2", color=COLORS["text_secondary"]),
            ),
            rx.form(
                rx.hstack(
                    rx.input(
                        name="template_name",
                        placeholder="새 보고서 유형명 (예: 먼슬리)",
                        size="3",
                        flex="1",
                    ),
                    rx.button("시작하기", type="submit", size="3",
                              style={"background": _ACCENT, "color": "white"}),
                    width="100%",
                ),
                on_submit=ReportMakerState.create_template,
                reset_on_submit=True,
                width="100%",
            ),
            spacing="4",
            width="100%",
            max_width="420px",
            padding="2em",
            border=f"1px solid {COLORS['border']}",
            border_radius=SPACING["border_radius_md"],
            bg=COLORS["sidebar_bg"],
            align="center",
        ),
        width="100%",
        height="100%",
    )


def _message(m: ReportMessage, idx: int) -> rx.Component:
    """단일 메시지 렌더 (user 버블 / assistant 마크다운 / 아웃라인)."""
    return rx.cond(
        m.role == "user",
        rx.box(
            rx.text(m.content, white_space="pre-wrap", color=COLORS["text_primary"]),
            align_self="flex-end",
            max_width="80%",
            padding="0.7em 1em",
            bg=COLORS["user_bubble"],
            border_radius=SPACING["border_radius_md"],
            margin_y="0.4em",
        ),
        rx.box(
            rx.markdown(m.content),
            rx.cond(
                m.is_outline,
                rx.hstack(
                    rx.button(
                        rx.icon("copy", size=14), "복사",
                        on_click=ReportMakerState.copy_message(idx),
                        variant="soft", color_scheme="gray", size="1",
                    ),
                    rx.button(
                        rx.icon("bookmark", size=14), "스타일 저장",
                        on_click=ReportMakerState.save_outline_style(idx),
                        variant="soft", color_scheme="gray", size="1",
                    ),
                    spacing="2",
                    margin_top="0.5em",
                ),
            ),
            align_self="flex-start",
            max_width="100%",
            width="100%",
            padding="0.4em 0.2em",
            margin_y="0.4em",
        ),
    )


def _chat_view() -> rx.Component:
    """세션 시작 후 — 대화/생성 흐름."""
    return rx.vstack(
        # 상단 바
        rx.hstack(
            _template_menu(),
            rx.button(
                rx.icon("plus", size=16), "새 대화",
                on_click=ReportMakerState.start_new_chat,
                variant="soft", color_scheme="gray", size="2",
            ),
            rx.cond(
                ReportMakerState.conversation_list.length() > 0,
                rx.menu.root(
                    rx.menu.trigger(
                        rx.button(
                            rx.icon("history", size=16), "이전 대화",
                            variant="soft", color_scheme="gray", size="2",
                        ),
                    ),
                    rx.menu.content(
                        rx.foreach(
                            ReportMakerState.conversation_list,
                            lambda c: rx.menu.item(
                                c.title,
                                on_click=ReportMakerState.load_conversation_by_id(c.id),
                            ),
                        ),
                    ),
                ),
            ),
            rx.button(
                rx.icon("upload", size=16), "참고 문서 등록",
                on_click=ReportMakerState.pick_and_upload_style,
                variant="soft", color_scheme="gray", size="2",
            ),
            rx.button(
                rx.icon("pencil-ruler", size=16), "작성 가이드",
                on_click=ReportMakerState.open_style_editor,
                variant="soft", color_scheme="gray", size="2",
            ),
            rx.spacer(),
            rx.cond(
                ReportMakerState.style_upload_status != "",
                rx.text(ReportMakerState.style_upload_status, size="1",
                        color=COLORS["text_secondary"]),
            ),
            width="100%",
            align="center",
            padding_bottom="0.5em",
            border_bottom=f"1px solid {COLORS['border']}",
        ),
        # 메시지 목록
        rx.box(
            rx.cond(
                ReportMakerState.messages.length() > 0,
                rx.vstack(
                    rx.foreach(ReportMakerState.messages, _message),
                    width="100%",
                    spacing="1",
                ),  # foreach 는 (item, index) 를 콜백에 전달 → _message(m, idx)
                rx.center(
                    rx.vstack(
                        rx.text("주제·목적·배경·경과·기대효과·향후 계획 등을 적어주시면",
                                size="3", color=COLORS["text_secondary"]),
                        rx.text("보고서 초안을 만들어 드립니다.",
                                size="3", color=COLORS["text_secondary"]),
                        rx.text("PPT·PDF·이미지도 첨부할 수 있습니다.",
                                size="1", color=COLORS["text_secondary"], margin_top="0.5em"),
                        align="center",
                    ),
                    width="100%",
                    height="100%",
                ),
            ),
            id="rm-chat-container",
            width="100%",
            flex="1",
            overflow_y="auto",
            padding_y="1em",
        ),
        # 입력 바
        rx.form(
            rx.hstack(
                rx.button(
                    rx.icon("paperclip", size=18),
                    on_click=ReportMakerState.pick_and_upload_topic,
                    type="button",
                    variant="soft", color_scheme="gray", size="3",
                ),
                rx.text_area(
                    name="message",
                    placeholder="보고할 내용을 입력하세요...",
                    disabled=ReportMakerState.is_streaming,
                    flex="1",
                    resize="none",
                    rows="2",
                    enter_key_submit=True,
                ),
                rx.button(
                    rx.cond(
                        ReportMakerState.is_streaming,
                        rx.icon("loader-circle", size=18, class_name="animate-spin"),
                        rx.icon("arrow-up", size=18),
                    ),
                    type="submit",
                    disabled=ReportMakerState.is_streaming,
                    size="3",
                    style={"background": _ACCENT, "color": "white"},
                ),
                width="100%",
                align="center",
            ),
            on_submit=ReportMakerState.send_message,
            reset_on_submit=True,
            width="100%",
        ),
        width="100%",
        height="100%",
        max_width="900px",
        margin="0 auto",
        spacing="2",
    )


def report_maker_page() -> rx.Component:
    """보고서 문구 작성 지원 페이지.

    rx.script 는 페이지 fragment 루트에 두어야(레이아웃 내부 깊숙이 X) mount 타이밍
    이슈 없이 window 전역 함수(reportMakerPickAndUpload)가 클릭 전에 정의된다.
    (report_checker.py 와 동일 패턴)
    """
    return rx.fragment(
        rx.script(REPORT_MAKER_SCRIPT),
        chat_layout(
            rx.box(
                rx.cond(
                    ReportMakerState.session_ready,
                    _chat_view(),
                    _setup_view(),
                ),
                width="100%",
                height="100%",
                padding="1.5em 2em",
            )
        ),
    )


def report_maker_style_page() -> rx.Component:
    """작성 가이드(스타일) 조회/편집 페이지 (/ai-services/report-generator/style)."""
    return chat_layout(
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.link(
                        rx.icon("arrow-left", size=18, color=COLORS["text_secondary"]),
                        href="/ai-services/report-generator",
                    ),
                    rx.heading("작성 가이드 편집", size="7", color=COLORS["text_primary"]),
                    rx.cond(
                        ReportMakerState.template_display != "",
                        rx.badge(
                            rx.icon("layout-template", size=14),
                            ReportMakerState.template_display,
                            color_scheme="gray", variant="soft", size="2",
                        ),
                    ),
                    align="center",
                    spacing="3",
                ),
                rx.text(
                    "현재 적용 중인 작성 가이드라인을 직접 확인·편집할 수 있습니다. "
                    "저장하면 이후 보고서 문구 생성에 즉시 반영됩니다.",
                    size="2",
                    color=COLORS["text_secondary"],
                ),
                rx.form(
                    rx.vstack(
                        rx.text_area(
                            name="edited_style",
                            default_value=ReportMakerState.edited_style,
                            placeholder=(
                                "아직 학습된 작성 가이드가 없습니다. 참고 문서를 등록하거나 "
                                "여기에 직접 작성해 저장하세요."
                            ),
                            rows="20",
                            width="100%",
                            style={"minHeight": "420px", "fontFamily": "monospace",
                                   "lineHeight": "1.6"},
                        ),
                        rx.hstack(
                            rx.spacer(),
                            rx.button(
                                rx.cond(
                                    ReportMakerState.is_streaming,
                                    rx.icon("loader-circle", size=16, class_name="animate-spin"),
                                    rx.icon("save", size=16),
                                ),
                                "저장",
                                type="submit",
                                disabled=ReportMakerState.is_streaming,
                                size="3",
                                style={"background": _ACCENT, "color": "white"},
                            ),
                            width="100%",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    on_submit=ReportMakerState.save_edited_style,
                    reset_on_submit=False,
                    width="100%",
                ),
                spacing="4",
                width="100%",
                max_width="900px",
                margin="0 auto",
            ),
            width="100%",
            height="100%",
            overflow_y="auto",
            padding="2.5em 2em",
        )
    )
