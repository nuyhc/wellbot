"""단일 편집기 스타일 모델 — memory.add_doc_style / set_style.

단일 편집기 전환: 스타일은 하나의 편집 가능한 정본(combined)이다.
- add_doc_style: 문서 추출본을 기존 정본에 병합(정본이 비면 그대로).
- set_style: 정본 전체를 편집 텍스트로 덮어쓴다.
AgentCore 미가용(순수 S3) 경로를 가짜 스토리지로 검증한다.
"""

from wellbot.services.report_maker import memory


class _FakeStorage:
    def __init__(self, combined=""):
        self.combined = combined

    def load_combined_style(self, emp_no, template):
        return self.combined

    def save_combined_style(self, emp_no, template, desc):
        self.combined = desc


def _patch(monkeypatch, fake):
    monkeypatch.setattr(memory, "storage", fake)
    monkeypatch.setattr(memory, "_agentcore_ready", lambda: False)
    # 병합은 결정적 스텁으로 — 실제 LLM 대신 '기존 + 신규' 결합 확인
    monkeypatch.setattr(
        memory.style, "merge_style_desc",
        lambda existing, new: f"{existing} || {new}" if existing.strip() else new,
    )


def test_add_doc_into_empty_takes_desc_verbatim(monkeypatch):
    fake = _FakeStorage(combined="")
    _patch(monkeypatch, fake)

    memory.add_doc_style("100", "주간", "개조식, 표 활용")

    assert fake.combined == "개조식, 표 활용"  # 정본이 비어 병합 없이 그대로


def test_add_doc_merges_over_existing(monkeypatch):
    fake = _FakeStorage(combined="기존 스타일")
    _patch(monkeypatch, fake)

    memory.add_doc_style("100", "주간", "새 문서 스타일")

    assert fake.combined == "기존 스타일 || 새 문서 스타일"  # 기존 위에 병합


def test_set_style_overwrites(monkeypatch):
    fake = _FakeStorage(combined="이전 내용")
    _patch(monkeypatch, fake)

    memory.set_style("100", "주간", "  사용자가 직접 쓴 스타일  ")

    assert fake.combined == "사용자가 직접 쓴 스타일"  # 병합 없이 전체 교체(+trim)


def test_delete_doc_does_not_touch_style(monkeypatch):
    fake = _FakeStorage(combined="유지되어야 함")
    _patch(monkeypatch, fake)
    # delete_doc 은 원본 파일만 지운다 — 정본 텍스트는 건드리지 않음
    monkeypatch.setattr(
        memory.storage, "delete_style_doc_file",
        lambda emp_no, template, basename: True, raising=False,
    )

    memory.delete_doc("100", "주간", "250101120000_a.pdf")

    assert fake.combined == "유지되어야 함"
