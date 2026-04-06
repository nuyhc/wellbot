"""메시지 입력 컴포넌트"""
import reflex as rx
from wellbot.state.chat import ChatState, MODEL_NAMES

_UPLOAD_ID = "file_upload_zone"
_BTN_UPLOAD_ID = "btn_upload_zone"

# popover 메뉴에서 숨겨진 upload 컴포넌트의 file input을 트리거하는 JS
_CLICK_BTN_UPLOAD = f"""
const el = document.getElementById("{_BTN_UPLOAD_ID}");
if (el) {{
    const input = el.querySelector("input[type=file]");
    if (input) input.click();
}}
"""


def _file_chip(file_info: dict) -> rx.Component:
    """첨부 파일 칩 — attached_files의 dict 항목을 받아 파일명 표시"""
    return rx.tooltip(
        rx.hstack(
            rx.icon("paperclip", size=14, color="rgba(255,255,255,0.6)"),
            rx.text(file_info["filename"], size="2", color="rgba(255,255,255,0.8)",
                    max_width="200px", overflow="hidden", text_overflow="ellipsis",
                    white_space="nowrap"),
            rx.icon(
                "x", size=14, color="rgba(255,255,255,0.5)", cursor="pointer",
                on_click=ChatState.remove_file(file_info["filename"]),
                _hover={"color": "white"},
            ),
            background="rgba(107, 33, 168, 0.3)",
            border="1px solid rgba(107, 33, 168, 0.5)",
            border_radius="14px",
            padding="0.3em 0.8em",
            align_items="center",
            gap="0.4em",
        ),
        content=file_info["filename"],
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
                # 파일 첨부 — JS로 숨겨진 upload input을 트리거 (popover 언마운트 문제 방지)
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
                    on_click=[
                        ChatState.set_plus_menu_open(False),
                        rx.call_script(_CLICK_BTN_UPLOAD),
                    ],
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
        open=ChatState.plus_menu_open,
        on_open_change=ChatState.set_plus_menu_open,
    )


def base_input_bar() -> rx.Component:
    return rx.box(
        # 숨겨진 파일 업로드 컴포넌트 (popover 밖에서 항상 마운트 — 파일 선택 대화상자용)
        rx.upload(
            rx.box(display="none"),
            id=_BTN_UPLOAD_ID,
            on_drop=ChatState.handle_upload(
                rx.upload_files(upload_id=_BTN_UPLOAD_ID)
            ),
            multiple=True,
            max_size=52_428_800,
            no_drag=True,
            no_click=True,
            position="absolute",
            width="1px",
            height="1px",
            overflow="hidden",
            opacity="0",
            pointer_events="none",
        ),

        # 업로드 진행 중 스피너
        rx.cond(
            ChatState.uploading,
            rx.hstack(
                rx.spinner(size="2"),
                rx.text("파일 처리 중...", size="2", color="rgba(255,255,255,0.6)"),
                align_items="center",
                gap="0.5em",
                padding="0 1.5em 0.5em 1.5em",
            ),
        ),

        # 업로드 에러 메시지 (파일 칩 목록 위에 표시)
        rx.cond(
            ChatState.upload_error != "",
            rx.text(
                ChatState.upload_error,
                color="red",
                size="2",
                padding="0 1.5em 0.5em 1.5em",
            ),
        ),

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

        # 입력바: + 버튼은 upload 존 바깥에 배치 (클릭 이벤트 충돌 방지)
        rx.form(
            rx.hstack(
                _plus_button(),

                # 드래그앤드랍 존 (textarea + 우측 컨트롤만 감싸기)
                rx.upload(
                    rx.hstack(
                        rx.text_area(
                            value=ChatState.question,
                            placeholder="WellBot에게 질문하세요!",
                            on_change=ChatState.set_question,
                            enter_key_submit=True,
                            auto_height=True,
                            style={
                                "flex": "1",
                                "background": "transparent",
                                "border": "none",
                                "color": "white",
                                "outline": "none",
                                "resize": "none",
                                "min_height": "40px",
                                "max_height": "200px",
                                "overflow_y": "auto",
                            },
                            id="message_input",
                        ),

                        rx.vstack(
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
                            rx.select(
                                MODEL_NAMES,
                                value=ChatState.selected_model,
                                on_change=ChatState.set_selected_model,
                                size="1",
                                variant="ghost",
                            ),
                            align_items="center",
                            spacing="1",
                        ),

                        flex="1",
                        align_items="center",
                    ),
                    id=_UPLOAD_ID,
                    on_drop=ChatState.handle_upload(
                        rx.upload_files(upload_id=_UPLOAD_ID)
                    ),
                    multiple=True,
                    max_size=52_428_800,
                    no_click=True,
                    flex="1",
                    border="none",
                    padding="0",
                ),

                width="100%",
                padding="0.6em 1em 0.6em 0.8em",
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

        rx.text(
            "WellBot은 실수를 할 수 있습니다. 생성형 AI의 출력 결과를 검증하고 활용하세요.",
            size="1",
            color="rgba(255, 255, 255, 0.35)",
            text_align="center",
            width="100%",
            padding_top="0.4em",
        ),

        width="100%",
        max_width="1200px",
        margin="0 auto",
        padding="1em 4em 0.8em 4em",
    )
