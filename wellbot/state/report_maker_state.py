"""보고서 문구 작성 지원 — Reflex 상태머신 (백지 재작성).

legacy ChatState 의 flow_stage 흐름을 동일 UX 로 재현하되:
- 신원은 사번 입력이 아니라 AuthState 세션의 emp_no (서버 도출)
- 서비스 로직은 report_maker 서비스 계층(analysis/structure/build/style)
- 영속은 db(대화·템플릿) / memory(AgentCore 스타일) / storage(S3 파일)
- 진행 상황은 async-generator + yield 로 UI 에 점진 반영

흐름:
  템플릿 선택/생성 → start_session(스타일 로드) → 주제 입력
  → analyze → await_page_count → [정보 게이트] → propose_structure → await_clarify
  → 1회 되묻기 → build → 편집 루프
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid

import reflex as rx
from pydantic import BaseModel

from wellbot.services.report_maker import (
    analysis,
    bedrock,
    build,
    db,
    memory,
    storage,
    structure,
    style,
)
from wellbot.services.report_maker.config import get_config
from wellbot.services.report_maker.parsing import (
    extract_questions,
    fmt_pages,
    md_linebreaks,
    parse_page_count,
    strip_question_block,
    to_safe_id,
)
from wellbot.state.auth_state import AuthState

log = logging.getLogger(__name__)

_SKIP_WORDS = ("진행", "그냥", "그대로", "없음", "TBD", "tbd", "진행해", "진행해줘")

MODE_INTRO = (
    "----------------------------------------------------\n\n"
    "## 보고 유형 안내\n"
    "이 에이전트는 두 가지 보고 유형을 지원합니다.\n\n"
    " **서머리 (정기 보고)** — 팀의 여러 과제를 한눈에 정리하는 정기 보고입니다.\n\n"
    " **심층 보고** — 하나의 주제/안건을 배경→검증→기대효과→향후 계획 흐름으로 깊이 풀어냅니다.\n\n"
    " ※ 보고유형은 입력한 토픽을 기반으로 에이전트가 자동 분류합니다.\n"
)


class ReportMessage(BaseModel):
    """대화 메시지(표시용). role="user"|"assistant", is_outline=최종 아웃라인."""

    role: str = "assistant"
    content: str = ""
    is_outline: bool = False
    is_flow: bool = False
    style_saved: bool = False
    file_name: str = ""


class ConvSummary(BaseModel):
    id: str = ""
    title: str = ""
    created_at: float = 0.0


class ReportMakerState(rx.State):
    # ── 신원 (백엔드 전용) ──
    _emp_no: str = ""

    # ── 템플릿(보고서 유형) ──
    template_id: str = ""
    template_display: str = ""
    templates: list[dict] = []
    show_new_template: bool = False
    show_template_menu: bool = False

    # ── 세션 ──
    session_ready: bool = False
    session_id: str = ""
    loaded_style: str = ""
    user_mode: str = ""          # "report_based" | "text_based"
    edited_style: str = ""

    # ── 대화 ──
    messages: list[ReportMessage] = []
    conversation_list: list[ConvSummary] = []
    is_streaming: bool = False
    show_guide: bool = False

    # ── 생성 흐름(flow) ──
    outline: str = ""
    iteration: int = 0
    flow_stage: str = ""
    pending_topic: str = ""
    flow_analysis: str = ""
    report_type: str = ""
    report_type_name: str = ""
    report_mode: str = "deep"
    report_storyline: str = ""
    report_storyline_blocks: str = ""
    deepdive_targets: str = ""
    page_count: float = 0
    recommended_pages: float = 0
    page_options: list[dict] = []
    proposed_structure: str = ""
    pending_questions: list[str] = []
    struct_gate_total: int = 0
    gate_asked_questions: list[str] = []
    outline_reasked: bool = False
    edit_instructions: list[str] = []

    # ── 업로드 ──
    style_upload_status: str = ""
    _uploaded_topic_text: str = ""

    # ── 영속 커서 (백엔드) ──
    _persisted_count: int = 0

    # ══════════════════════════════════════════════════════════
    # computed
    # ══════════════════════════════════════════════════════════
    @rx.var
    def is_report_based(self) -> bool:
        return self.user_mode == "report_based"

    @rx.var
    def has_templates(self) -> bool:
        return len(self.templates) > 0

    @rx.var
    def recent_chats_label(self) -> str:
        return "최근 대화" if self.conversation_list else ""

    # ══════════════════════════════════════════════════════════
    # 진입 / 인증
    # ══════════════════════════════════════════════════════════
    @rx.event
    async def on_load(self):
        auth = await self.get_state(AuthState)
        self._emp_no = auth.current_emp_no
        if not self._emp_no:
            return rx.redirect("/login")
        await self._load_templates()

    async def _load_templates(self):
        self.templates = await asyncio.to_thread(db.list_templates, self._emp_no)

    # ══════════════════════════════════════════════════════════
    # 템플릿(보고서 유형)
    # ══════════════════════════════════════════════════════════
    @rx.event
    def toggle_new_template(self):
        self.show_new_template = not self.show_new_template

    @rx.event
    def toggle_template_menu(self):
        self.show_template_menu = not self.show_template_menu

    @rx.event
    def close_template_menu(self):
        self.show_template_menu = False

    @rx.event
    async def select_template(self, template_id: str):
        t = await asyncio.to_thread(db.get_template, self._emp_no, template_id)
        self.template_id = template_id
        self.template_display = t["display"] if t else template_id
        self.show_template_menu = False
        async for _ in self._start_session():
            yield

    @rx.event
    async def create_template(self, form_data: dict):
        name = (form_data.get("template_name") or "").strip()
        if not name:
            yield rx.toast.error("보고서 유형명을 입력해주세요.")
            return
        tid = to_safe_id(name)
        actor = memory.actor_id_for(self._emp_no, tid)
        ok = await asyncio.to_thread(db.save_template, self._emp_no, tid, name, actor)
        if not ok:
            yield rx.toast.error(f"보고서 유형은 최대 {get_config().max_templates}개까지 가능합니다.")
            return
        await self._load_templates()
        self.template_id = tid
        self.template_display = name
        self.show_new_template = False
        async for _ in self._start_session():
            yield

    @rx.event
    async def delete_template(self, template_id: str):
        await asyncio.to_thread(db.delete_template, self._emp_no, template_id)
        await asyncio.to_thread(storage.delete_template_files, self._emp_no, template_id)
        await self._load_templates()
        if self.template_id == template_id:
            self.session_ready = False
            self.template_id = ""
            self.template_display = ""

    # ══════════════════════════════════════════════════════════
    # 세션
    # ══════════════════════════════════════════════════════════
    async def _start_session(self):
        self.is_streaming = True
        yield
        self.loaded_style = await asyncio.to_thread(
            memory.load_style, self._emp_no, self.template_id
        )
        self.user_mode = "report_based" if self.loaded_style.strip() else "text_based"
        self._reset_conversation()
        self.session_id = uuid.uuid4().hex[:50]
        self.session_ready = True
        await self._load_conversation_list()
        self.is_streaming = False
        yield

    def _reset_conversation(self):
        """새 대화 초기화. 새 상태 변수는 반드시 여기에만 추가한다."""
        self.messages = []
        self.outline = ""
        self.iteration = 0
        self.flow_stage = ""
        self.pending_topic = ""
        self.flow_analysis = ""
        self.report_type = ""
        self.report_type_name = ""
        self.report_mode = "deep"
        self.report_storyline = ""
        self.report_storyline_blocks = ""
        self.deepdive_targets = ""
        self.page_count = 0
        self.recommended_pages = 0
        self.page_options = []
        self.proposed_structure = ""
        self.pending_questions = []
        self.struct_gate_total = 0
        self.gate_asked_questions = []
        self.outline_reasked = False
        self.edit_instructions = []
        self._uploaded_topic_text = ""
        self._persisted_count = 0

    @rx.event
    async def start_new_chat(self):
        self._reset_conversation()
        self.session_id = uuid.uuid4().hex[:50]
        await self._load_conversation_list()

    # ══════════════════════════════════════════════════════════
    # 대화 이력 (chtb_smry_d / chtb_msg_d, AGNT_ID 태깅)
    # ══════════════════════════════════════════════════════════
    async def _load_conversation_list(self):
        rows = await asyncio.to_thread(db.list_conversations, self._emp_no)
        self.conversation_list = [
            ConvSummary(id=r["id"], title=r["title"], created_at=r["created_at"]) for r in rows
        ]

    @rx.event
    async def load_conversation_list(self):
        await self._load_conversation_list()

    @rx.event
    async def load_conversation_by_id(self, session_id: str):
        rows = await asyncio.to_thread(
            db.get_conversation_messages, session_id, self._emp_no
        )
        self._reset_conversation()
        self.session_id = session_id
        msgs: list[ReportMessage] = []
        last_outline = ""
        for r in rows:
            is_outline = r["role"] == "outline"
            role = "assistant" if is_outline else r["role"]
            msgs.append(ReportMessage(role=role, content=r["content"], is_outline=is_outline))
            if is_outline:
                last_outline = r["content"]
        self.messages = msgs
        self.outline = last_outline  # 편집 이어가기 복원 (flow_state 는 비영속)
        self._persisted_count = len(msgs)

    @rx.event
    async def delete_conversation_by_id(self, session_id: str):
        await asyncio.to_thread(db.delete_conversation, session_id, self._emp_no)
        if session_id == self.session_id:
            await self.start_new_chat()
        else:
            await self._load_conversation_list()

    @rx.event
    async def rename_conversation(self, session_id: str, new_title: str):
        await asyncio.to_thread(
            db.update_conversation_title, session_id, new_title, self._emp_no
        )
        await self._load_conversation_list()

    async def _persist_turn(self):
        """이번 턴에서 확정된 새 메시지를 DB 에 append (flow_state 는 저장 안 함)."""
        if not self.messages:
            return
        title = next(
            (m.content[:30] for m in self.messages if m.role == "user"), "새 대화"
        )
        await asyncio.to_thread(db.save_conversation, self._emp_no, self.session_id, title)
        new = self.messages[self._persisted_count:]
        for m in new:
            role = "outline" if m.is_outline else m.role
            await asyncio.to_thread(
                db.append_message, self.session_id, role, m.content, self._emp_no
            )
        self._persisted_count = len(self.messages)
        await self._load_conversation_list()

    # ══════════════════════════════════════════════════════════
    # 스타일 학습 (업로드 → 분석 → AgentCore/S3 저장)
    # ══════════════════════════════════════════════════════════
    @rx.event(background=True)
    async def on_style_uploaded(self, key: str):
        """API 업로드가 반환한 S3 key 를 받아 문서 스타일을 학습한다."""
        async with self:
            emp_no, template = self._emp_no, self.template_id
            self.style_upload_status = "스타일 분석 중..."
            self.is_streaming = True

        def worker() -> str:
            path = storage.download_to_temp(key)
            try:
                doc = style.extract_doc_style(path)
                analyzed = style.analyze_style_with_claude(doc)
                desc = style.build_style_desc(doc, analyzed)
                memory.save_style(emp_no, template, desc)
                return desc
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass

        try:
            await asyncio.to_thread(worker)
            async with self:
                self.loaded_style = await asyncio.to_thread(
                    memory.load_style, self._emp_no, self.template_id
                )
                self.user_mode = "report_based"
                self.style_upload_status = "스타일 학습 완료"
                self.is_streaming = False
        except Exception:
            log.exception("스타일 학습 실패 key=%s", key)
            async with self:
                self.style_upload_status = "스타일 학습에 실패했습니다. 다시 시도해주세요."
                self.is_streaming = False

    @rx.event
    async def on_topic_uploaded(self, key: str):
        """주제 첨부 파일의 텍스트를 추출해 다음 입력에 합친다."""
        self.is_streaming = True
        yield

        def worker() -> str:
            path = storage.download_to_temp(key)
            try:
                if style.is_image_file(path):
                    return style.extract_text_from_image(path)
                return style.extract_plain_text(path)
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass

        try:
            text = await asyncio.to_thread(worker)
            self._uploaded_topic_text = text or ""
        except Exception:
            log.exception("주제 첨부 처리 실패 key=%s", key)
        self.is_streaming = False
        yield

    # ══════════════════════════════════════════════════════════
    # 스타일 편집
    # ══════════════════════════════════════════════════════════
    @rx.event
    def set_edited_style(self, value: str):
        self.edited_style = value

    @rx.event
    def open_style_editor(self):
        self.edited_style = self.loaded_style
        return rx.redirect("/ai-services/report-generator/style")

    @rx.event
    async def save_edited_style(self, form_data: dict):
        edited = (form_data.get("edited_style") or "").strip()
        if not edited:
            yield rx.toast.error("스타일 내용을 입력해주세요.")
            return
        self.is_streaming = True
        yield
        await asyncio.to_thread(storage.save_combined_style, self._emp_no, self.template_id, edited)
        await asyncio.to_thread(memory.save_preference, self._emp_no, self.template_id, edited)
        self.loaded_style = edited
        self.is_streaming = False
        yield rx.toast.success("스타일 저장 완료")

    # ══════════════════════════════════════════════════════════
    # UI 토글 / 유틸
    # ══════════════════════════════════════════════════════════
    @rx.event
    def toggle_guide(self):
        self.show_guide = not self.show_guide

    @rx.event
    def copy_message(self, idx: int):
        if not (0 <= idx < len(self.messages)):
            return
        content = self.messages[idx].content
        escaped = content.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
        return rx.call_script(f"navigator.clipboard.writeText(`{escaped}`)")

    @rx.event
    async def save_outline_style(self, idx: int):
        """생성된 아웃라인을 이 템플릿의 선호 스타일로 저장."""
        if not (0 <= idx < len(self.messages)):
            return
        content = self.messages[idx].content
        await asyncio.to_thread(memory.save_preference, self._emp_no, self.template_id, content)
        self.messages[idx] = self.messages[idx].copy(update={"style_saved": True})
        yield rx.toast.success("현재 스타일을 저장했습니다.")

    # ══════════════════════════════════════════════════════════
    # 메인 입력 처리
    # ══════════════════════════════════════════════════════════
    @rx.event
    async def send_message(self, form_data: dict):
        text = (form_data.get("message") or "").strip()
        if not text or self.is_streaming:
            return
        # 주제 첨부 텍스트가 있으면 합침
        if self._uploaded_topic_text:
            text = f"{self._uploaded_topic_text}\n[추가지시]\n{text}"
            self._uploaded_topic_text = ""
        self.messages.append(ReportMessage(role="user", content=text))
        yield
        try:
            async for _ in self._route(text):
                yield
        finally:
            await self._persist_turn()
            yield

    async def _route(self, user_input: str):
        stage = self.flow_stage
        if stage == "await_page_count":
            async for _ in self._handle_page_count(user_input):
                yield
        elif stage == "await_clarify":
            async for _ in self._handle_flow_clarify(user_input):
                yield
        elif stage == "await_deep_info":
            async for _ in self._handle_deep_info(user_input):
                yield
        elif stage == "await_struct_info":
            async for _ in self._handle_struct_info(user_input):
                yield
        elif stage == "await_outline_info":
            async for _ in self._handle_outline_info(user_input):
                yield
        else:
            intent = await asyncio.to_thread(self._classify_intent, user_input)
            if intent == "edit" and self.outline:
                async for _ in self._edit_outline(user_input):
                    yield
            elif intent == "outline":
                self.outline = ""
                self.iteration = 0
                async for _ in self._start_flow(user_input):
                    yield
            else:
                async for _ in self._handle_general_chat(user_input):
                    yield

    # ── STEP 1: 주제 분석 ──
    async def _start_flow(self, topic: str):
        self.is_streaming = True
        self.messages.append(ReportMessage(content="분석 중..."))
        yield

        a = await asyncio.to_thread(
            analysis.analyze_topic, topic, self.loaded_style, self.user_mode == "report_based"
        )
        if not a:
            self.messages[-1] = ReportMessage(content="분석에 실패했습니다. 다시 시도해주세요.")
            self.is_streaming = False
            yield
            return

        self.pending_topic = topic
        self.report_type = a.get("report_type", "")
        self.report_type_name = a.get("report_type_name", "")
        _mode = a.get("mode", "")
        self.report_mode = _mode if _mode in ("summary", "deep") else "deep"
        self.report_storyline = a.get("storyline", "")

        blocks = a.get("storyline_blocks", []) or []
        block_lines = []
        for i, b in enumerate(blocks, 1):
            nm = (b.get("name", "") if isinstance(b, dict) else str(b)).strip()
            dt = (b.get("detail", "") if isinstance(b, dict) else "").strip()
            block_lines.append(f"  {i}. {nm}" + (f" — {dt}" if dt else ""))
        blocks_text = "\n".join(block_lines)
        self.report_storyline_blocks = blocks_text

        self.flow_analysis = (
            f"목적: {a.get('purpose','')}\n현재 상태: {a.get('current_state','')}\n"
            f"핵심 메시지: {a.get('key_message','')}\n논리 흐름: {a.get('storyline','')}"
            + (f"\n논리 블록:\n{blocks_text}" if blocks_text else "")
        )
        self.page_options = a.get("page_options", [])
        self.recommended_pages = a.get("recommended_pages", 0)
        opts = "\n".join(f"* {o.get('label','')}" for o in self.page_options)
        mode_label = "서머리" if self.report_mode == "summary" else "심층 보고"

        self.flow_stage = "await_page_count"
        self.messages[-1] = ReportMessage(
            content=(
                "## **파악한 내용**\n"
                f"- 목적: {a.get('purpose','')}\n- 현재 상태: {a.get('current_state','')}\n"
                f"- 핵심 메시지: {a.get('key_message','')}\n"
                + (f"- 제안 흐름:\n{md_linebreaks(blocks_text)}\n\n" if blocks_text
                   else f"- 제안 흐름: {md_linebreaks(a.get('storyline',''))}\n\n")
                + f"이 내용은 **{self.report_type_name} ({mode_label})** 보고서가 적합해 보입니다.\n"
                "보고 유형을 바꾸고 싶으면 알려주세요.\n"
                "* 추천 (적정 분량을 제가 정해 드립니다)\n"
                f"{opts}\n\n"
                "몇 장 구조로 작성할까요? 정해진 분량이 있으면 골라주시고, 없으면 **추천**이라고 답해 주세요.\n\n"
                + md_linebreaks(MODE_INTRO)
            ),
            is_flow=True,
        )
        self.is_streaming = False
        yield

    # ── STEP 2: 페이지 수 → 정보 게이트 → 구조 제안 ──
    async def _handle_page_count(self, user_input: str):
        self.is_streaming = True
        yield
        _u = user_input.strip()
        used_recommend = False

        if any(k in _u for k in ("추천", "알아서", "정해줘", "적당", "골라")):
            used_recommend = True
            pages_list = [float(o.get("pages", 0)) for o in self.page_options if o.get("pages") is not None]
            rec = None
            try:
                cand_rec = float(self.recommended_pages)
                if cand_rec in pages_list:
                    rec = cand_rec
            except (TypeError, ValueError):
                rec = None
            if rec is None:
                cand = sorted(p for p in pages_list if p >= 1) or sorted(pages_list)
                rec = cand[0] if cand else None
            self.page_count = rec if rec is not None else 1
        else:
            self.page_count = parse_page_count(user_input)

        chosen_label = self._chosen_label()

        # 정보 충실도 게이트 (심층 · 3장 이상 · 추천보다 많이 고른 경우)
        try:
            rec = float(self.recommended_pages)
        except (TypeError, ValueError):
            rec = 0
        if (self.report_mode == "deep" and float(self.page_count) >= 3
                and (rec <= 0 or float(self.page_count) > rec)):
            check = await asyncio.to_thread(
                structure.check_page_info, self.pending_topic, self.flow_analysis, self.page_count, rec
            )
            questions = (check or {}).get("questions", [])
            if not (check or {}).get("sufficient", True) and questions:
                self.pending_questions = questions
                self.struct_gate_total = len(questions)
                self.gate_asked_questions = list(questions)
                self.outline_reasked = False
                q_text = "  \n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))
                rec_phrase = f"적정 분량은 {int(rec)}장 내외이며, " if rec > 0 else ""
                self.messages.append(ReportMessage(content=(
                    f"{rec_phrase}{int(float(self.page_count))}장을 채우려면 아래 정보가 더 필요합니다.\n\n"
                    f"{q_text}\n\n---\n답을 입력해 주세요. 모르는 항목은 'TBD', 지금 정보로 진행하려면 '진행'."
                )))
                self.flow_stage = "await_struct_info"
                self.is_streaming = False
                yield
                return

        proposal = await asyncio.to_thread(
            structure.propose_structure, self.pending_topic, self.flow_analysis,
            self.report_type_name, self.page_count, self.report_mode, chosen_label,
            self.loaded_style, self.user_mode == "report_based",
            self.report_storyline, self.report_storyline_blocks,
        )
        self.proposed_structure = proposal["structure"]

        # 서머리 다장: 심층 정보 게이트 블록
        if self.report_mode == "summary" and float(self.page_count) >= 2 and not self.deepdive_targets:
            check = await asyncio.to_thread(
                structure.check_deepdive_info, self.pending_topic, self.flow_analysis,
                self.proposed_structure, self.page_count, chosen_label,
            )
            self.deepdive_targets = ", ".join(check.get("deep_targets", [])) if check else "done"
            deep_qs = (check or {}).get("questions", []) if not (check or {}).get("sufficient", True) else []
            if deep_qs:
                block = ("\n\n**!!  심층 보고 작성을 위해 추가 정보가 필요합니다 (반드시 입력)**\n"
                         + "\n".join(f"{i}. {q}" for i, q in enumerate(deep_qs, 1)))
                self.proposed_structure = self.proposed_structure + block

        self.pending_questions = extract_questions(self.proposed_structure)
        await self._apply_grounding()
        self.outline_reasked = False

        rec_note = (f"적정 분량으로 **{fmt_pages(self.page_count)}장**을 추천드립니다. 다른 분량을 원하시면 알려주세요.\n\n"
                    if used_recommend else "")
        self.messages.append(ReportMessage(content=(
            rec_note + md_linebreaks(self.proposed_structure)
            + "\n\n---\n이 구조로 진행할까요? 수정할 점이 있으면 알려주세요."
        )))
        self.flow_stage = "await_clarify"
        self.is_streaming = False
        yield

    async def _apply_grounding(self):
        """근거 검증 패스: 구조가 요구하나 입력에 근거 없는 항목을 질문으로 추가."""
        try:
            asked = list(self.pending_questions or []) + list(self.gate_asked_questions or [])
            ground_qs = await asyncio.to_thread(
                structure.check_grounding, self.pending_topic, self.flow_analysis,
                self.proposed_structure, asked,
            )
        except Exception:
            log.exception("[근거검증] 실패(무시)")
            ground_qs = []
        ground_qs = [q for q in (ground_qs or []) if q and q not in (self.pending_questions or [])]
        if ground_qs:
            self.pending_questions = list(self.pending_questions or []) + ground_qs
            self.proposed_structure = structure.merge_ground_questions(self.proposed_structure, ground_qs)

    def _chosen_label(self) -> str:
        for o in self.page_options:
            try:
                if float(o.get("pages", 0)) == float(self.page_count):
                    return o.get("label", "")
            except (TypeError, ValueError):
                continue
        return ""

    # ── STEP 3: 구조 확인/수정 ──
    async def _handle_flow_clarify(self, user_input: str):
        self.is_streaming = True
        yield
        _u = user_input.strip()

        import re
        page_change = re.fullmatch(
            r"\s*(\d+(?:\.\d+)?)\s*(?:장|페이지|쪽)(?:으로|로)?\s*(?:바꿔|바꿔줘|해줘|변경|줄여|늘려|해)?\s*", _u
        )
        if page_change:
            new_pc = float(page_change.group(1))
            if new_pc != float(self.page_count):
                self.page_count = new_pc
                proposal = await asyncio.to_thread(
                    structure.propose_structure, self.pending_topic, self.flow_analysis,
                    self.report_type_name, self.page_count, self.report_mode, self._chosen_label(),
                    self.loaded_style, self.user_mode == "report_based",
                    self.report_storyline, self.report_storyline_blocks,
                )
                self.proposed_structure = proposal["structure"]
                self.messages.append(ReportMessage(content=(
                    f"**{fmt_pages(self.page_count)}장** 구조로 다시 제안드립니다.\n\n"
                    + md_linebreaks(proposal["structure"])
                    + "\n\n---\n이 구조로 진행할까요? 수정할 점이 있으면 알려주세요."
                )))
                self.flow_stage = "await_clarify"
                self.is_streaming = False
                yield
                return

        self.proposed_structure += f"\n[추가 요청] {user_input}"
        self.pending_topic += f"\n[추가 정보] {user_input}"
        if self.pending_questions and _u not in _SKIP_WORDS:
            self.pending_questions = await asyncio.to_thread(
                structure.remaining_questions, self.pending_questions, user_input
            )

        if (not self.outline_reasked) and self.pending_questions:
            q_text = "  \n".join(f"{i}. {q}" for i, q in enumerate(self.pending_questions, 1))
            self.messages.append(ReportMessage(content=(
                "아웃라인 작성 전 마지막으로 확인합니다. 정보를 입력하시면 반영하고, "
                "'진행'이라고 하시면 해당 항목은 (TBD)로 두고 작성합니다.\n\n" + q_text
            )))
            self.outline_reasked = True
            self.flow_stage = "await_outline_info"
            self.is_streaming = False
            yield
            return

        self.flow_stage = ""
        async for _ in self._run_build():
            yield

    async def _handle_deep_info(self, user_input: str):
        self.is_streaming = True
        yield
        self.proposed_structure += f"\n[심층 과제 추가정보] {user_input}"
        self.pending_topic += f"\n[심층 과제 추가정보] {user_input}"
        self.flow_stage = ""
        async for _ in self._run_build():
            yield

    async def _handle_struct_info(self, user_input: str):
        self.is_streaming = True
        yield
        _u = user_input.strip()
        skip = _u in _SKIP_WORDS
        if not skip:
            self.pending_topic += f"\n[추가 정보] {_u}"
            self.flow_analysis += f"\n[추가 정보] {_u}"
            if self.pending_questions:
                self.pending_questions = await asyncio.to_thread(
                    structure.remaining_questions, self.pending_questions, _u
                )

        total = self.struct_gate_total or 0
        remaining = len(self.pending_questions)
        answered_ratio = 0.0 if (skip or total <= 0) else (total - remaining) / total
        try:
            rec = float(self.recommended_pages)
        except (TypeError, ValueError):
            rec = 0
        if answered_ratio < 0.5 and rec > 0 and rec < float(self.page_count):
            self.page_count = rec
            self.messages.append(ReportMessage(content=(
                f"입력하신 정보가 요청하신 분량을 채우기에 부족하여, 적정 분량인 "
                f"**{fmt_pages(rec)}장**으로 구조를 제안드립니다."
            )))

        proposal = await asyncio.to_thread(
            structure.propose_structure, self.pending_topic, self.flow_analysis,
            self.report_type_name, self.page_count, self.report_mode, self._chosen_label(),
            self.loaded_style, self.user_mode == "report_based",
            self.report_storyline, self.report_storyline_blocks,
        )
        self.proposed_structure = proposal["structure"]
        self.pending_questions = extract_questions(self.proposed_structure)
        await self._apply_grounding()
        self.outline_reasked = False
        self.messages.append(ReportMessage(content=(
            md_linebreaks(proposal["structure"])
            + "\n\n---\n이 구조로 진행할까요? 수정할 점이 있으면 알려주세요."
        )))
        self.flow_stage = "await_clarify"
        self.is_streaming = False
        yield

    async def _handle_outline_info(self, user_input: str):
        self.is_streaming = True
        yield
        _u = user_input.strip()
        if _u not in _SKIP_WORDS:
            self.pending_topic += f"\n[추가 정보] {_u}"
            self.flow_analysis += f"\n[추가 정보] {_u}"
            if self.pending_questions:
                self.pending_questions = await asyncio.to_thread(
                    structure.remaining_questions, self.pending_questions, _u
                )
        self.flow_stage = ""
        async for _ in self._run_build():
            yield

    # ── STEP 4: 아웃라인 빌드 ──
    async def _run_build(self):
        self.messages.append(ReportMessage(content="초안 생성 중..."))
        yield
        outline = await asyncio.to_thread(
            build.build_outline, self.pending_topic, self.loaded_style,
            strip_question_block(self.proposed_structure), self.report_type,
            self.report_type_name, self.page_count, self.report_mode,
            self.report_storyline, self.report_storyline_blocks,
            self.pending_questions, self.user_mode == "report_based",
        )
        if not outline:
            self.messages[-1] = ReportMessage(content="생성에 실패했습니다. 다시 시도해주세요.")
            self.is_streaming = False
            yield
            return
        self.outline = outline
        self.iteration = 0
        self.edit_instructions = []
        self.messages[-1] = ReportMessage(
            content=md_linebreaks(outline)
            + "\n\n---\n수정 요청사항을 입력하거나, 현재 스타일을 저장하세요.",
            is_outline=True,
        )
        self.is_streaming = False
        yield

    # ── 편집 루프 ──
    async def _edit_outline(self, feedback: str):
        self.is_streaming = True
        self.messages.append(ReportMessage(content="아웃라인 수정 중..."))
        yield
        self.edit_instructions = self.edit_instructions + [feedback.strip()]
        outline = await asyncio.to_thread(
            build.edit_outline, self.outline, feedback, self.report_mode,
            self.page_count, self.edit_instructions, self.pending_questions,
        )
        if not outline:
            self.messages[-1] = ReportMessage(content="수정에 실패했습니다. 다시 시도해주세요.")
            self.is_streaming = False
            yield
            return
        self.outline = outline
        self.iteration += 1
        self.messages[-1] = ReportMessage(
            content=md_linebreaks(outline) + f"\n\n수정 완료 (#{self.iteration})",
            is_outline=True,
        )
        self.is_streaming = False
        yield

    # ── 의도 분류 (동기, to_thread 로 호출) ──
    def _classify_intent(self, user_input: str) -> str:
        has_outline = bool(self.outline)
        prompt = (
            "사용자 입력을 분류하세요.\n\n"
            f"[현재 상태] 아웃라인 {'보유 중' if has_outline else '없음'}\n\n"
            f"[사용자 입력]\n{user_input}\n\n"
            "분류 기준:\n"
            "- outline : 새로운 주제/토픽 제시. 아웃라인 없음 상태에서 내용이 들어오면 거의 항상 outline.\n"
            "- edit    : 아웃라인 보유 중 + 수정 요청(수정·바꿔·추가·삭제·줄여·늘려) 또는 수치·일정·근거 등 새 값 보완.\n"
            "- chat    : 아웃라인 보유 중 + 내용을 바꾸지 않고 묻기만 하는 후속 질문, 또는 무관한 잡담.\n"
            "outline, edit, chat 중 하나만 출력하세요."
        )
        result = bedrock.call_model(prompt, 5000).strip().lower()
        if "edit" in result:
            return "edit"
        if "chat" in result:
            return "chat"
        return "outline"

    async def _handle_general_chat(self, user_input: str):
        self.messages.append(ReportMessage(content="답변 생성 중..."))
        yield
        context = ""
        if self.loaded_style:
            context += "[사용자 문서 스타일]\n" + self.loaded_style + "\n\n"
        if self.pending_topic:
            context += "[사용자가 입력한 원본 내용]\n" + self.pending_topic + "\n\n"
        if self.outline:
            context += "[현재 아웃라인]\n" + self.outline + "\n\n"
        prompt = (
            context + "[사용자 질문]\n" + user_input + "\n\n"
            "사용자의 질문에 친절하고 자연스럽게 답변하세요. 아웃라인 내용의 출처를 물으면 "
            "[원본 내용]과 대조해 정직하게 답하세요(입력에 있으면 '입력하신 내용', 없으면 보고서 구성을 위해 작성한 부분).\n"
        )
        answer = await asyncio.to_thread(bedrock.call_model, prompt, 5000)
        self.messages[-1] = ReportMessage(content=answer or "답변을 생성하지 못했습니다.")
        self.is_streaming = False
        yield

    # ══════════════════════════════════════════════════════════
    # 로그아웃
    # ══════════════════════════════════════════════════════════
    @rx.event
    async def logout(self):
        auth = await self.get_state(AuthState)
        self._reset_conversation()
        self.session_ready = False
        self.template_id = ""
        self.template_display = ""
        self._emp_no = ""
        return AuthState.logout
