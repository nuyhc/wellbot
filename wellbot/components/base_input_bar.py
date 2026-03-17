"""메시지 입력 컴포넌트"""
import reflex as rx
from ..state.chat import ChatState

_UPLOAD_ID = "file_upload_zone"
_BTN_UPLOAD_ID = "btn_upload_zone"


def _file_chip(filename: str) -> rx.Component:
    return rx.hstack(
        rx.icon("paperclip", size=12, color="rgba(255,255,255,0.6)"),
        rx.text(filename, size="1", color="rgba(255,255,255,0.8)", max_width="150px",
                overflow="hidden", text_overflow="ellipsis", white_space="nowrap"),
        rx.icon(
            "x", size=12, color="rgba(255,255,255,0.5)", cursor="pointer",
            on_click=ChatState.remove_file(filename),
            _hover={"color": "white"},
        ),
        background="rgba(107, 33, 168, 0.3)",
        border="1px solid rgba(107, 33, 168, 0.5)",
        border_radius="12px",
        padding="0.2em 0.6em",
        align_items="center",
        gap="0.3em",
    )


def _plus_button() -> rx.Component:
    """+ 버튼 → popover 메뉴 (파일 첨부 / Extended Thinking 토글)"""
    return rx.popover.root(
        rx.popover.trigger(
            rx.icon_button(
                rx.icon("plus", size=18),
                variant="ghost",
                color=rx.cond(
                    ChatState.thinking_enabled,
                    "#a855f7",            # thinking ON → 보라색
                    "rgba(255,255,255,0.6)",
                ),
                width="36px",
                height="36px",
                border_radius="50%",
                cursor="pointer",
                _hover={"background": "rgba(255,255,255,0.1)", "color": "white"},
            ),
        ),
        rx.popover.content(
            rx.vstack(
                # 파일 첨부
                rx.upload(
                    rx.hstack(
                        rx.icon("paperclip", size=15, color="rgba(255,255,255,0.7)"),
                        rx.text("파일 첨부", size="2", color="rgba(255,255,255,0.9)"),
                        width="100%",
                        align_items="center",
                        gap="0.5em",
                        padding="0.4em 0.6em",
                        border_radius="8px",
                        cursor="pointer",
                        _hover={"background": "rgba(255,255,255,0.08)"},
                    ),
                    id=_BTN_UPLOAD_ID,
                    on_drop=ChatState.handle_upload(
                        rx.upload_files(upload_id=_BTN_UPLOAD_ID)
                    ),
                    multiple=True,
                    no_drag=True,
                    border="none",
                    padding="0",
                    width="100%",
                ),

                # Extended Thinking 토글 (지원 모델만 표시)
                rx.cond(
                    ChatState.current_model_supports_thinking,
                    rx.hstack(
                        rx.icon("brain", size=15, color="rgba(255,255,255,0.7)"),
                        rx.text(
                            "Extended Thinking",
                            size="2",
                            color="rgba(255,255,255,0.9)",
                        ),
                        rx.spacer(),
                        rx.switch(
                            checked=ChatState.thinking_enabled,
                            on_change=ChatState.toggle_thinking,
                            color_scheme="violet",
                        ),
                        width="100%",
                        align_items="center",
                        gap="0.5em",
                        padding="0.4em 0.6em",
                    ),
                ),

                gap="0.2em",
                min_width="200px",
            ),
            background="rgba(20, 22, 30, 0.97)",
            border="1px solid rgba(255,255,255,0.1)",
            border_radius="12px",
            padding="0.4em",
            box_shadow="0 8px 32px rgba(0,0,0,0.5)",
            side="top",
            align="start",
        ),
    )


def base_input_bar() -> rx.Component:
    return rx.box(
        # 첨부 파일 칩 목록
        rx.cond(
            ChatState.attached_files.length() > 0,
            rx.hstack(
                rx.foreach(ChatState.attached_files, _file_chip),
                flex_wrap="wrap",
                gap="0.4em",
                padding="0 1.5em 0.5em 1.5em",
            ),
        ),

        # 드래그앤드랍 존 (전체 입력바)
        rx.upload(
            rx.form(
                rx.hstack(
                    _plus_button(),

                    rx.input(
                        value=ChatState.question,
                        placeholder="WellBot에게 질문하세요!",
                        on_change=ChatState.set_question,
                        style={
                            "flex": "1",
                            "background": "transparent",
                            "border": "none",
                            "color": "white",
                            "outline": "none",
                        },
                        id="message_input",
                    ),

                    rx.button(
                        rx.icon("send", size=18, color="white"),
                        type="submit",
                        loading=ChatState.processing,
                        background="linear-gradient(135deg, #6b21a8, #3b82f6)",
                        border_radius="50%",
                        width="40px",
                        height="40px",
                        padding="0",
                        display="flex",
                        align_items="center",
                        justify_content="center",
                        _hover={
                            "transform": "scale(1.05)",
                            "box_shadow": "0 0 15px rgba(107, 33, 168, 0.5)",
                        },
                        cursor="pointer",
                    ),

                    width="100%",
                    padding="0.5em 0.5em 0.5em 0.8em",
                    background="rgba(30, 32, 40, 0.8)",
                    border_radius="30px",
                    border="1px solid rgba(255, 255, 255, 0.1)",
                    box_shadow="0 4px 20px rgba(0, 0, 0, 0.3)",
                    align_items="center",
                ),
                on_submit=ChatState.answer,
                reset_on_submit=True,
                width="100%",
            ),
            id=_UPLOAD_ID,
            on_drop=ChatState.handle_upload(
                rx.upload_files(upload_id=_UPLOAD_ID)
            ),
            multiple=True,
            no_click=True,
            width="100%",
            border="none",
            padding="0",
        ),

        width="100%",
        max_width="1200px",
        margin="0 auto",
        padding="1em 4em 2em 4em",
    )
