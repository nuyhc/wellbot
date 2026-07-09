"""보고서 오류 검출 State.

흐름:
  1. pick_file → 브라우저 파일 선택 (reportPickFile)
  2. start_analysis → 업로드 (reportUpload) → job_id 수신
  3. analyze (background) → S3 원본 다운로드 → 페이지 추출 → 분석(진행률 통지)
     → 결과 HTML S3 저장 → presigned 다운로드 URL 발급 → 결과 State 반영
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

import reflex as rx

from wellbot.services.report_checker import storage
from wellbot.services.report_checker.models import ProgressEvent, UserDictionary
from wellbot.services.report_checker.pdf_extract import extract_pages_from_bytes
from wellbot.services.report_checker.pipeline import run_analysis
from wellbot.services.report_checker.report_html import generate_html
from wellbot.state.auth_state import AuthState

log = logging.getLogger(__name__)


class ReportCheckerState(rx.State):
    """보고서 오류 검출 페이지 상태."""

    # ── 입력 ──
    pending_file_name: str = ""
    pending_file_size: int = 0
    exclusions_text: str = ""       # 제외어 (콤마/줄바꿈 구분)
    synonyms_text: str = ""         # 동의어 (한 줄 = 한 그룹, 콤마 구분)
    include_consistency: bool = False  # 일관성 검사 포함 여부 (기본: 오탈자만, 일관성은 선택)
    ran_consistency: bool = True    # 이번 결과에 일관성 검사가 실제 수행됐는지

    # ── 진행 ──
    status: str = "idle"        # idle | uploading | analyzing | done | error
    stage: str = ""             # parsing | typo | consistency | done
    progress_pct: int = 0
    progress_detail: str = ""
    typo_count: int = 0
    consistency_count: int = 0
    error_message: str = ""

    # ── 결과 ──
    job_id: str = ""
    source_file_name: str = ""
    typo_errors: list[dict] = []
    consistency_errors: list[dict] = []
    download_url: str = ""

    # ── 파생 ──
    @rx.var
    def is_running(self) -> bool:
        return self.status in ("uploading", "analyzing")

    @rx.var
    def has_file(self) -> bool:
        return bool(self.pending_file_name)

    @rx.var
    def has_result(self) -> bool:
        return self.status == "done"

    @rx.var
    def total_errors(self) -> int:
        return self.typo_count + self.consistency_count

    @rx.var
    def file_size_label(self) -> str:
        if self.pending_file_size <= 0:
            return ""
        mb = self.pending_file_size / (1024 * 1024)
        return f"{mb:.1f} MB"

    # ── 입력 세터 ──
    def set_exclusions_text(self, value: str) -> None:
        self.exclusions_text = value

    def set_synonyms_text(self, value: str) -> None:
        self.synonyms_text = value

    def set_include_consistency(self, value: bool) -> None:
        self.include_consistency = value

    # ── 파일 선택 ──
    def pick_file(self):
        return rx.call_script(
            "reportPickFile()", callback=ReportCheckerState.on_file_picked
        )

    def on_file_picked(self, meta):
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = None
        if not meta:
            return
        self.pending_file_name = meta.get("name", "")
        self.pending_file_size = int(meta.get("size", 0) or 0)

    # ── 분석 시작 ──
    def start_analysis(self):
        if not self.has_file:
            return rx.toast.error("PDF 파일을 먼저 선택해주세요.")
        self.status = "uploading"
        self.stage = ""
        self.error_message = ""
        self.typo_errors = []
        self.consistency_errors = []
        self.typo_count = 0
        self.consistency_count = 0
        self.download_url = ""
        self.progress_pct = 0
        self.progress_detail = "업로드 중..."
        return rx.call_script(
            "reportUpload()", callback=ReportCheckerState.on_uploaded
        )

    def on_uploaded(self, result):
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                result = {"error": result}
        if not result or result.get("error") or not result.get("job_id"):
            self.status = "error"
            self.error_message = (result or {}).get("error") or "업로드에 실패했습니다."
            return
        self.job_id = result["job_id"]
        self.source_file_name = result.get("filename") or self.pending_file_name
        self.status = "analyzing"
        self.stage = "parsing"
        self.progress_detail = "PDF 분석 준비 중..."
        return ReportCheckerState.analyze

    def _parse_dictionary(self) -> UserDictionary:
        exclusions = [t.strip() for t in re.split(r"[\n,]", self.exclusions_text) if t.strip()]
        groups: list[list[str]] = []
        for line in self.synonyms_text.splitlines():
            terms = [t.strip() for t in line.split(",") if t.strip()]
            if len(terms) >= 2:
                groups.append(terms)
        return UserDictionary(exclusions=exclusions, synonym_groups=groups)

    def _apply_progress(self, evt: ProgressEvent) -> None:
        self.stage = evt.stage
        if evt.detail:
            self.progress_detail = evt.detail
        if evt.typo_count:
            self.typo_count = evt.typo_count
        if evt.consistency_count:
            self.consistency_count = evt.consistency_count
        total = evt.total or 1
        if evt.stage == "parsing":
            self.progress_pct = 5
        elif evt.stage == "typo":
            # 일관성 검사가 없으면 오탈자만으로 5→95% 사용
            span = 45 if self.include_consistency else 90
            self.progress_pct = 5 + int(span * evt.current / total)
        elif evt.stage == "consistency":
            self.progress_pct = 50 + int(45 * evt.current / total)
        elif evt.stage == "done":
            self.progress_pct = 100

    @rx.event(background=True)
    async def analyze(self):
        """S3 원본을 읽어 분석 실행. 진행률은 큐로 받아 UI 갱신."""
        auth = await self.get_state(AuthState)
        emp_no = auth.current_emp_no
        async with self:
            job_id = self.job_id
            source_name = self.source_file_name
            dictionary = self._parse_dictionary()
            do_consistency = self.include_consistency

        if not emp_no or not job_id:
            async with self:
                self.status = "error"
                self.error_message = "세션 정보를 확인할 수 없습니다. 다시 로그인해주세요."
            return

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def on_progress(evt: ProgressEvent) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, evt)

        def worker():
            data = storage.download_source(emp_no, job_id)
            pages = extract_pages_from_bytes(data)
            if not pages:
                raise RuntimeError("PDF 에서 텍스트를 추출하지 못했습니다. 스캔본 PDF 는 지원하지 않습니다.")
            on_progress(
                ProgressEvent(
                    stage="parsing",
                    detail=f"{len(pages)}개 페이지 추출 완료",
                    total=len(pages),
                )
            )
            return run_analysis(
                pages, dictionary, on_progress, do_consistency=do_consistency
            )

        task = asyncio.create_task(asyncio.to_thread(worker))
        try:
            while not (task.done() and queue.empty()):
                try:
                    evt = await asyncio.wait_for(queue.get(), timeout=0.15)
                except asyncio.TimeoutError:
                    continue
                async with self:
                    self._apply_progress(evt)
            result = await task
        except Exception as e:  # noqa: BLE001 - UI 에 표면화
            log.exception("report_checker 분석 실패 job_id=%s", job_id)
            async with self:
                self.status = "error"
                self.error_message = str(e)
            return

        # 결과 HTML 생성 + S3 저장 + 다운로드 URL (블로킹은 스레드로)
        html = generate_html(result, source_name, consistency_checked=do_consistency)
        stem = Path(source_name).stem or "report"
        filename = f"{stem}_검출결과.html"

        def finalize() -> str:
            storage.save_result_html(emp_no, job_id, html)
            return storage.result_download_url(emp_no, job_id, filename=filename)

        try:
            url = await asyncio.to_thread(finalize)
        except Exception as e:  # noqa: BLE001
            log.exception("report_checker 결과 저장 실패 job_id=%s", job_id)
            url = ""

        async with self:
            self.typo_errors = [e.to_dict() for e in result.typo_errors]
            # 중첩 foreach 를 피하기 위해 표시용 문자열을 미리 합쳐 둔다.
            self.consistency_errors = [
                {
                    **e.to_dict(),
                    "values_str": " vs ".join(str(v) for v in e.values),
                    "pages_str": ", ".join(f"{p}p" for p in sorted(e.pages)),
                }
                for e in result.consistency_errors
            ]
            self.typo_count = len(result.typo_errors)
            self.consistency_count = len(result.consistency_errors)
            self.ran_consistency = do_consistency
            self.download_url = url
            self.status = "done"
            self.stage = "done"
            self.progress_pct = 100
            self.progress_detail = "분석 완료"

    def reset_checker(self):
        """새 분석을 위해 상태 초기화."""
        self.status = "idle"
        self.stage = ""
        self.pending_file_name = ""
        self.pending_file_size = 0
        self.exclusions_text = ""
        self.synonyms_text = ""
        self.include_consistency = False
        self.ran_consistency = False
        self.progress_pct = 0
        self.progress_detail = ""
        self.typo_count = 0
        self.consistency_count = 0
        self.error_message = ""
        self.job_id = ""
        self.source_file_name = ""
        self.typo_errors = []
        self.consistency_errors = []
        self.download_url = ""
