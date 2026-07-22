"""보고서 문구 작성 지원 페이지.

chat_layout 으로 래핑(표준 wellbot 사이드바 유지)하고, 메인 영역에 보고서 유형 선택
→ 대화(생성 흐름) UI 를 렌더한다. 업로드는 커스텀 API(fetch) 로 처리한다.
"""

import reflex as rx

from wellbot.components.layout import chat_layout
from wellbot.state.report_maker_scripts import (
    REPORT_MAKER_AUTOSCROLL_SCRIPT,
    REPORT_MAKER_SCRIPT,
)
from wellbot.state.report_maker_state import ReportMakerState, ReportMessage
from wellbot.styles import COLORS, MARKDOWN_COMPONENT_MAP, SPACING

_ACCENT = "#E97055"


def _template_menu_row(t) -> rx.Component:
    """드롭다운의 유형 1행 — 선택(전환) + 작성 스타일 바로가기 + 이름 변경 + 삭제(확인)."""
    return rx.hstack(
        rx.text(
            t["display"], size="2", color=COLORS["text_primary"],
            cursor="pointer", flex="1",
            on_click=ReportMakerState.select_template(t["id"]),
        ),
        # 작성 스타일 편집 바로가기
        rx.icon_button(
            rx.icon("palette", size=14),
            on_click=ReportMakerState.edit_template_style(t["id"]),
            variant="ghost", color_scheme="gray", size="1", title="작성 스타일 편집",
        ),
        # 이름 변경
        rx.dialog.root(
            rx.dialog.trigger(
                rx.icon_button(rx.icon("pencil", size=14), variant="ghost",
                               color_scheme="gray", size="1", title="이름 변경"),
            ),
            rx.dialog.content(
                rx.dialog.title("이름 변경"),
                rx.form(
                    rx.vstack(
                        rx.input(name="template_name", default_value=t["display"],
                                 placeholder="보고서 유형명", size="3", width="100%"),
                        rx.hstack(
                            rx.dialog.close(
                                rx.button("취소", type="button", variant="soft",
                                          color_scheme="gray"),
                            ),
                            rx.dialog.close(
                                rx.button("저장", type="submit",
                                          style={"background": _ACCENT, "color": "white"}),
                            ),
                            spacing="2", justify="end", width="100%",
                        ),
                        spacing="3", width="100%",
                    ),
                    on_submit=ReportMakerState.rename_template(t["id"]),
                    reset_on_submit=False,
                ),
                max_width="360px",
            ),
        ),
        # 삭제(확인)
        rx.alert_dialog.root(
            rx.alert_dialog.trigger(
                rx.icon_button(rx.icon("trash-2", size=14), variant="ghost",
                               color_scheme="red", size="1", title="삭제"),
            ),
            rx.alert_dialog.content(
                rx.alert_dialog.title("보고서 유형 삭제"),
                rx.alert_dialog.description(
                    "이 유형의 대화·작성 스타일·참고 문서가 모두 삭제됩니다. 되돌릴 수 없습니다.",
                ),
                rx.hstack(
                    rx.alert_dialog.cancel(
                        rx.button("취소", variant="soft", color_scheme="gray"),
                    ),
                    rx.alert_dialog.action(
                        rx.button("삭제", color_scheme="red",
                                  on_click=ReportMakerState.delete_template(t["id"])),
                    ),
                    spacing="3", justify="end", margin_top="1em",
                ),
            ),
        ),
        width="100%",
        align="center",
        padding="0.4em 0.6em",
        _hover={"background": COLORS["sidebar_hover"]},
        border_radius=SPACING["border_radius_sm"],
    )


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
                    rx.foreach(ReportMakerState.templates, _template_menu_row),
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
    """유형 0개(첫 사용)일 때만 보이는 생성 화면. 유형이 있으면 on_load 가 자동 진입한다.

    유형은 있는데 세션이 아직 준비 중인 짧은 순간에는 생성 폼 대신 로딩만 보여
    '첫 유형 만들기'가 잘못 노출되지 않게 한다.
    """
    return rx.center(
        rx.cond(
            ReportMakerState.has_templates,
            # 자동 진입 중(유형은 있으나 세션 준비 전) — 잠깐 로딩
            rx.vstack(
                rx.spinner(size="3"),
                rx.text("불러오는 중...", size="2", color=COLORS["text_secondary"]),
                spacing="3", align="center",
            ),
            # 첫 사용 — 보고서 유형 생성
            rx.vstack(
                rx.icon("sparkles", size=32, color=_ACCENT),
                rx.heading("보고서 문구 작성 지원", size="6", color=COLORS["text_primary"]),
                rx.text(
                    "첫 보고서 유형을 만들어 시작하세요.",
                    size="2", color=COLORS["text_secondary"],
                ),
                rx.form(
                    rx.hstack(
                        rx.input(
                            name="template_name",
                            placeholder="새 보고서 유형명 (예: 먼슬리)",
                            size="3", flex="1",
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
        ),
        width="100%",
        height="100%",
    )


def _message(m: ReportMessage, idx: int) -> rx.Component:
    """단일 메시지 렌더 — 메인 챗과 동일 시각 언어(user 우측 버블 / assistant 좌측 마크다운)."""
    return rx.cond(
        m.role == "user",
        # 사용자: 우측 정렬 버블 (chat user_message 규격)
        rx.hstack(
            rx.box(
                rx.vstack(
                    rx.cond(
                        m.file_name != "",
                        rx.hstack(
                            rx.icon("paperclip", size=12, color=COLORS["text_secondary"]),
                            rx.text(m.file_name, size="1", color=COLORS["text_secondary"]),
                            rx.icon("download", size=12, color=COLORS["text_secondary"]),
                            align="center",
                            spacing="1",
                            cursor="pointer",
                            title="다운로드",
                            on_click=ReportMakerState.download_attachment(m.file_no),
                        ),
                    ),
                    rx.text(m.content, size="3", white_space="pre-wrap",
                            word_break="break-word", color=COLORS["text_primary"]),
                    spacing="1",
                    align="start",
                    width="100%",
                ),
                bg=COLORS["user_bubble"],
                padding="0.75em 1.25em",
                border_radius=SPACING["border_radius"],
                max_width="70%",
            ),
            class_name="chat-msg",
            width="100%",
            justify="end",
            padding_x="1em",
        ),
        # AI: 대기 중이면 스피너+문구 인디케이터(챗 loading_indicator 통일), 아니면 마크다운
        rx.cond(
            m.is_loading,
            rx.hstack(
                rx.spinner(size="2"),
                rx.text(m.content, size="2", color=COLORS["text_secondary"]),
                spacing="2",
                align="center",
                class_name="chat-msg",
                width="100%",
                padding_x="1em",
            ),
            rx.box(
                rx.markdown(m.content, component_map=MARKDOWN_COMPONENT_MAP),
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
                class_name="chat-msg",
                width="100%",
                color=COLORS["text_primary"],
                padding_x="1em",
            ),
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
            rx.spacer(),
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
                    max_width=SPACING["message_max_width"],
                    margin_x="auto",
                    spacing="4",
                    padding_y="1.5em",
                ),  # foreach 는 (item, index) 를 콜백에 전달 → _message(m, idx)
                rx.center(
                    rx.vstack(
                        rx.text("주제·목적·배경·경과·기대효과·향후 계획 등을 적어주시면",
                                size="3", color=COLORS["text_secondary"]),
                        rx.text("보고서 초안을 만들어 드립니다.",
                                size="3", color=COLORS["text_secondary"]),
                        rx.text("PPT·PDF·이미지도 첨부할 수 있습니다.",
                                size="1", color=COLORS["text_secondary"], margin_top="0.5em"),
                        # ── 상세 작성 가이드 토글 (입력 항목 1~6 안내) ──
                        rx.button(
                            rx.cond(
                                ReportMakerState.show_guide,
                                rx.hstack(rx.text("상세 작성 가이드 접기"),
                                          rx.icon("chevron-up", size=16), align="center", spacing="1"),
                                rx.hstack(rx.text("상세 작성 가이드 보기"),
                                          rx.icon("chevron-down", size=16), align="center", spacing="1"),
                            ),
                            on_click=ReportMakerState.toggle_guide,
                            type="button",
                            variant="soft", color_scheme="gray", size="2",
                            margin_top="1em",
                        ),
                        rx.cond(
                            ReportMakerState.show_guide,
                            rx.vstack(
                                rx.text("1. 어떤 주제인가요?  (보고서로 다루려는 과제·사안)"),
                                rx.text("2. 보고서의 목적은?  (의사결정·지원 요청 / 현황 공유 / 성과 보고)"),
                                rx.text("3. 왜 하는 업무인가요?  (배경 - 왜 중요한가, 어떤 문제·기회인가)"),
                                rx.text("4. 진행 경과는?  (진행한 일, 검증 결과, 수치, 일정)"),
                                rx.text("5. 기대효과는?  (회사에 어떤 가치인가? - 리스크 감소, 상담 콜수 감소)"),
                                rx.text("6. 향후 계획과 필요한 의사결정은?  (다음 단계 + 결정·지원할 사항)"),
                                rx.text("* 모르는 항목은 비워두셔도 됩니다.",
                                        size="1", color=COLORS["text_secondary"], margin_top="0.3em"),
                                align="start",
                                spacing="1",
                                margin_top="0.8em",
                                padding="1em 1.2em",
                                bg=COLORS["sidebar_bg"],
                                border=f"1px solid {COLORS['border']}",
                                border_radius=SPACING["border_radius_md"],
                                max_width="560px",
                                color=COLORS["text_primary"],
                                font_size="0.9em",
                            ),
                        ),
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
        # 입력 바 — 메인 챗 input_bar 룩 통일(둥근 박스 + 하단 파일첨부/전송). 파일 첨부만 유지.
        rx.box(
            rx.form(
                rx.vstack(
                    # 대기 중 첨부 칩(전송 전) — 첨부됐음을 명확히 표시
                    rx.cond(
                        ReportMakerState.pending_topic_file != "",
                        rx.hstack(
                            rx.icon("paperclip", size=13, color=COLORS["text_secondary"]),
                            rx.text(ReportMakerState.pending_topic_file, size="1",
                                    color=COLORS["text_primary"]),
                            rx.icon("x", size=13, color=COLORS["text_secondary"],
                                    cursor="pointer",
                                    on_click=ReportMakerState.clear_pending_topic),
                            align="center",
                            spacing="1",
                            padding="0.25em 0.6em",
                            bg=COLORS["sidebar_hover"],
                            border_radius=SPACING["border_radius_sm"],
                        ),
                    ),
                    # 텍스트 입력 (투명 배경, 자동 높이)
                    rx.text_area(
                        name="message",
                        placeholder="보고할 내용을 입력하세요...",
                        enter_key_submit=True,
                        auto_height=True,
                        variant="soft",
                        style={
                            "width": "100%",
                            "background": "transparent",
                            "box_shadow": "none",
                            "color": COLORS["text_primary"],
                            "font_size": "0.9375rem",
                            "line_height": "1.5",
                            "outline": "none",
                            "resize": "none",
                            "min_height": "24px",
                            "max_height": "150px",
                            "overflow_y": "auto",
                            "padding": "0",
                            "& textarea::placeholder": {"color": COLORS["text_secondary"]},
                        },
                    ),
                    # 하단: 파일 첨부(좌) + 전송(우)
                    rx.hstack(
                        rx.icon_button(
                            rx.icon("paperclip", size=16),
                            on_click=ReportMakerState.pick_and_upload_topic,
                            type="button",
                            variant="ghost",
                            size="2",
                            cursor="pointer",
                            color=COLORS["text_secondary"],
                            _hover={"color": COLORS["text_primary"],
                                    "bg": COLORS["tool_btn_hover"]},
                            border_radius="50%",
                        ),
                        rx.spacer(),
                        rx.cond(
                            ReportMakerState.is_streaming,
                            rx.icon_button(
                                rx.spinner(size="2"),
                                size="2", variant="solid", type="button", disabled=True,
                                border_radius="50%",
                                bg=COLORS["tool_btn_bg"], color=COLORS["text_secondary"],
                            ),
                            rx.icon_button(
                                rx.icon("arrow-up", size=16),
                                size="2", variant="solid", type="submit",
                                cursor="pointer", border_radius="50%",
                                bg=COLORS["text_primary"], color=COLORS["main_bg"],
                                _hover={"bg": COLORS["accent_hover"]},
                            ),
                        ),
                        width="100%",
                        align="center",
                        spacing="2",
                    ),
                    spacing="2",
                    padding="0.75em 1em",
                ),
                on_submit=ReportMakerState.send_message,
                reset_on_submit=True,
                width="100%",
            ),
            bg=COLORS["input_bg"],
            border_radius=SPACING["border_radius"],
            border=f"1px solid {COLORS['input_border']}",
            width="100%",
            max_width=SPACING["message_max_width"],
            margin_x="auto",
            _focus_within={"border_color": COLORS["accent_hover"]},
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
        rx.script(REPORT_MAKER_AUTOSCROLL_SCRIPT),
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
    """작성 스타일 조회/편집 페이지 (/ai-services/report-generator/style)."""
    return rx.fragment(
        # 스타일 추출(참고 문서 업로드) JS 헬퍼 — 편집기에서 추출 버튼이 동작하려면 필요.
        rx.script(REPORT_MAKER_SCRIPT),
        chat_layout(
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.link(
                        rx.icon("arrow-left", size=18, color=COLORS["text_secondary"]),
                        href="/ai-services/report-generator",
                    ),
                    rx.heading("작성 스타일 편집", size="7", color=COLORS["text_primary"]),
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
                    "현재 적용 중인 작성 스타일을 직접 확인·편집할 수 있습니다. "
                    "저장하면 이후 보고서 문구 생성에 즉시 반영됩니다.",
                    size="2",
                    color=COLORS["text_secondary"],
                ),
                # 참고 문서 목록 (등록 · 추출 · 초기화)
                rx.box(
                    rx.hstack(
                        rx.icon("files", size=16, color=COLORS["text_secondary"]),
                        rx.text("참고 문서", size="2", weight="medium",
                                color=COLORS["text_primary"]),
                        rx.badge(ReportMakerState.style_docs.length(),
                                 color_scheme="gray", variant="soft", size="1"),
                        rx.spacer(),
                        # 등록: 파일 선택·업로드만 (추출 안 함)
                        rx.button(
                            rx.icon("plus", size=14),
                            "문서 등록",
                            on_click=ReportMakerState.register_style_docs,
                            variant="soft", color_scheme="gray", size="1",
                            disabled=ReportMakerState.is_streaming,
                        ),
                        # 추출: 미추출 문서를 스타일에 반영(업데이트). 미추출 없으면 비활성.
                        rx.button(
                            rx.cond(
                                ReportMakerState.is_streaming,
                                rx.spinner(size="1"),
                                rx.icon("scan-text", size=14),
                            ),
                            rx.cond(
                                ReportMakerState.pending_extract_count > 0,
                                f"스타일 추출 ({ReportMakerState.pending_extract_count})",
                                "스타일 추출",
                            ),
                            on_click=ReportMakerState.extract_pending_styles,
                            variant="solid", color_scheme="gray", size="1",
                            disabled=ReportMakerState.is_streaming
                            | (ReportMakerState.pending_extract_count == 0),
                        ),
                        rx.alert_dialog.root(
                            rx.alert_dialog.trigger(
                                rx.button(
                                    rx.icon("trash-2", size=14), "작성 스타일 초기화",
                                    variant="soft", color_scheme="red", size="1",
                                    disabled=ReportMakerState.is_streaming,
                                ),
                            ),
                            rx.alert_dialog.content(
                                rx.alert_dialog.title("작성 스타일 초기화"),
                                rx.alert_dialog.description(
                                    "작성 스타일과 등록된 참고 문서가 모두 삭제됩니다. "
                                    "이 작업은 되돌릴 수 없습니다.",
                                ),
                                rx.hstack(
                                    rx.alert_dialog.cancel(
                                        rx.button("취소", variant="soft", color_scheme="gray"),
                                    ),
                                    rx.alert_dialog.action(
                                        rx.button("초기화", color_scheme="red",
                                                  on_click=ReportMakerState.reset_style),
                                    ),
                                    spacing="3", justify="end", margin_top="1em",
                                ),
                            ),
                        ),
                        width="100%", align="center", spacing="2",
                    ),
                    rx.cond(
                        ReportMakerState.style_upload_status != "",
                        rx.text(ReportMakerState.style_upload_status, size="1",
                                color=COLORS["text_secondary"], margin_top="0.4em"),
                    ),
                    rx.cond(
                        ReportMakerState.style_docs.length() > 0,
                        rx.vstack(
                            rx.foreach(
                                ReportMakerState.style_docs,
                                lambda d: rx.hstack(
                                    rx.icon("file-text", size=13,
                                            color=COLORS["text_secondary"]),
                                    rx.text(d["name"], size="1", color=COLORS["text_primary"]),
                                    rx.cond(
                                        d["extracted"],
                                        rx.badge("추출됨", color_scheme="green",
                                                 variant="soft", size="1"),
                                        rx.badge("미추출", color_scheme="amber",
                                                 variant="soft", size="1"),
                                    ),
                                    rx.spacer(),
                                    rx.icon("x", size=13, color=COLORS["text_secondary"],
                                            cursor="pointer", title="문서 삭제",
                                            on_click=ReportMakerState.delete_style_doc(d["key"])),
                                    align="center", spacing="1", width="100%",
                                ),
                            ),
                            spacing="1", align="start", margin_top="0.5em", width="100%",
                        ),
                        rx.text("아직 등록한 문서가 없습니다. '문서 등록'으로 참고 문서를 올리세요.",
                                size="1", color=COLORS["text_secondary"], margin_top="0.4em"),
                    ),
                    width="100%",
                    padding="0.8em 1em",
                    border=f"1px solid {COLORS['border']}",
                    border_radius=SPACING["border_radius_md"],
                    bg=COLORS["sidebar_bg"],
                ),
                # 작성 스타일 — 추출본+수동편집 통합 단일 편집기
                rx.hstack(
                    rx.text("작성 스타일", size="2", weight="medium",
                            color=COLORS["text_primary"]),
                    align="center", spacing="1",
                ),
                rx.text(
                    "문서에서 추출된 내용이 여기에 반영되어 있습니다. 직접 수정한 뒤 저장하세요. "
                    "'스타일 추출'로 문서를 추가하면 이 내용 위에 병합됩니다.",
                    size="1", color=COLORS["text_secondary"],
                ),
                rx.form(
                    rx.vstack(
                        rx.text_area(
                            name="edited_style",
                            value=ReportMakerState.edited_style,
                            on_change=ReportMakerState.set_edited_style,
                            placeholder=(
                                "작성 스타일을 자유롭게 편집하세요 (예: 문장 종결·톤·표 활용 등). "
                                "'스타일 추출'로 참고 문서를 올리면 여기에 자동 반영됩니다."
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
                                    rx.spinner(size="2"),
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
        ),
    )
