"""메시지 입력 바 컴포넌트.

ChatGPT/Claude 스타일 입력 바.
파일 첨부 버튼 + 텍스트 입력 + 모델 선택 팝오버 + 전송 버튼.

모델 선택 팝오버: 모델 목록 + 확장 사고 토글을 하나의 드롭다운으로 통합.
"""

import reflex as rx

from wellbot.state.chat_state import ChatState, ModelInfo
from wellbot.styles import COLORS, SPACING


def _model_item(model: ModelInfo) -> rx.Component:
    """팝오버 내 개별 모델 항목."""
    return rx.popover.close(
        rx.hstack(
            rx.vstack(
                rx.text(
                    model.name,
                    size="1",
                    weight="medium",
                ),
                rx.text(
                    model.description,
                    font_size="11px",
                    color=COLORS["text_secondary"],
                ),
                spacing="0",
                align_items="start",
            ),
            rx.spacer(),
            # 체크 아이콘 자리를 항상 확보하여 정렬 유지
            rx.box(
                rx.cond(
                    model.name == ChatState.selected_model,
                    rx.icon("check", size=14, color=COLORS["accent"]),
                ),
                width="16px",
                display="flex",
                align_items="center",
                justify_content="center",
                flex_shrink="0",
            ),
            width="100%",
            align="center",
            padding="0.35em 0.6em",
            border_radius=SPACING["border_radius_sm"],
            cursor="pointer",
            _hover={"bg": COLORS["sidebar_hover"]},
            on_click=ChatState.set_model(model.name),
        ),
        # popover.close에도 width 100% 적용
        width="100%",
    )


def _thinking_toggle_row() -> rx.Component:
    """확장 사고 토글 행. 미지원 모델에서는 비활성화 상태로 표시."""
    return rx.hstack(
        rx.vstack(
            rx.text(
                "확장 사고",
                size="1",
                weight="medium",
                color=rx.cond(
                    ChatState.model_supports_thinking,
                    COLORS["text_primary"],
                    COLORS["text_secondary"],
                ),
            ),
            rx.text(
                rx.cond(
                    ChatState.model_supports_thinking,
                    "복잡한 작업을 위해 더 오래 사고",
                    "확장 사고 미지원 모델",
                ),
                font_size="11px",
                color=COLORS["text_secondary"],
            ),
            spacing="0",
            align_items="start",
            flex="1",
            min_width="0",
        ),
        rx.switch(
            checked=rx.cond(
                ChatState.model_supports_thinking,
                ChatState.thinking_enabled,
                False,
            ),
            on_change=ChatState.toggle_thinking,
            disabled=~ChatState.model_supports_thinking,
            size="1",
            flex_shrink="0",
        ),
        width="100%",
        align="center",
        gap="0.5em",
        padding="0.35em 0.6em",
        opacity=rx.cond(ChatState.model_supports_thinking, "1", "0.5"),
    )


def _model_popover() -> rx.Component:
    """Claude 스타일 모델 선택 팝오버."""
    return rx.popover.root(
        rx.popover.trigger(
            rx.button(
                rx.text(
                    ChatState.trigger_label,
                    size="1",
                    weight="medium",
                ),
                rx.icon("chevron-down", size=14),
                variant="ghost",
                size="1",
                cursor="pointer",
                color=COLORS["text_secondary"],
                _hover={"color": COLORS["text_primary"]},
                type="button",
            ),
        ),
        rx.popover.content(
            rx.vstack(
                # 모델 목록
                rx.foreach(ChatState.model_list, _model_item),
                # 구분선
                rx.separator(size="4", color=COLORS["border"]),
                # 확장 사고 토글
                _thinking_toggle_row(),
                spacing="1",
                width="100%",
            ),
            side="top",
            align="end",
            style={
                "width": "250px",
                "padding": "0.4em",
                "border_radius": SPACING["border_radius_md"],
                "bg": COLORS["sidebar_bg"],
                "border": f"1px solid {COLORS['border']}",
                "box_shadow": "0 4px 24px rgba(0,0,0,0.25)",
            },
        ),
    )


def input_bar() -> rx.Component:
    """하단 고정 메시지 입력 바."""
    return rx.box(
        rx.vstack(
            # 입력 컨테이너 (둥근 박스)
            rx.box(
                rx.form(
                    rx.vstack(
                        # 텍스트 입력 영역
                        rx.text_area(
                            value=ChatState.current_input,
                            placeholder="WellBot에게 질문하세요!",
                            on_change=ChatState.set_input,
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
                                "& textarea::placeholder": {
                                    "color": COLORS["text_secondary"],
                                },
                            },
                        ),
                        # 하단: 첨부 + 모델 팝오버 + 전송
                        rx.hstack(
                            # 파일 첨부 버튼
                            rx.tooltip(
                                rx.icon_button(
                                    rx.icon("paperclip", size=16),
                                    variant="ghost",
                                    size="2",
                                    cursor="pointer",
                                    color=COLORS["text_secondary"],
                                    _hover={
                                        "color": COLORS["text_primary"],
                                        "bg": COLORS["tool_btn_hover"],
                                    },
                                    border_radius="50%",
                                    type="button",
                                ),
                                content="파일 첨부",
                            ),
                            rx.spacer(),
                            # 모델 선택 팝오버
                            _model_popover(),
                            # 전송 버튼
                            rx.icon_button(
                                rx.icon("arrow-up", size=16),
                                size="2",
                                variant="solid",
                                type="submit",
                                disabled=~ChatState.can_send,
                                loading=ChatState.is_loading,
                                cursor=rx.cond(
                                    ChatState.can_send,
                                    "pointer",
                                    "not-allowed",
                                ),
                                border_radius="50%",
                                bg=rx.cond(
                                    ChatState.can_send,
                                    COLORS["text_primary"],
                                    COLORS["tool_btn_bg"],
                                ),
                                color=rx.cond(
                                    ChatState.can_send,
                                    COLORS["main_bg"],
                                    COLORS["text_secondary"],
                                ),
                                _hover={
                                    "bg": rx.cond(
                                        ChatState.can_send,
                                        COLORS["accent_hover"],
                                        COLORS["tool_btn_bg"],
                                    ),
                                },
                            ),
                            width="100%",
                            align="center",
                            spacing="2",
                        ),
                        spacing="2",
                        padding="0.75em 1em",
                    ),
                    on_submit=ChatState.send_message,
                ),
                bg=COLORS["input_bg"],
                border_radius=SPACING["border_radius"],
                border=f"1px solid {COLORS['input_border']}",
                width="100%",
                max_width=SPACING["message_max_width"],
                margin_x="auto",
                _focus_within={
                    "border_color": COLORS["accent_hover"],
                },
            ),
            # 하단 안내 텍스트
            rx.text(
                "Wellbot은 실수할 수 있습니다. WellBot의 출력 결과를 확인하고 활용하세요.",
                size="1",
                color=COLORS["text_secondary"],
                text_align="center",
            ),
            spacing="2",
            width="100%",
            align="center",
        ),
        width="100%",
        padding_x="1em",
        padding_top="0.75em",
        padding_bottom="1em",
        bg=COLORS["main_bg"],
        flex_shrink="0",
    )
