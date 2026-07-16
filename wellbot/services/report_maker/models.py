"""report_maker 서비스 계층 데이터 모델 (순수 dataclass).

UI 표시용 pydantic 모델(ReportMessage 등)은 상태 계층(P4)에서 chat_models 를
확장해 정의한다 — 서비스 로직은 Reflex/pydantic 에 의존하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StorylineBlock:
    """분석 단계가 도출한 논리 블록. 이후 구조·분량이 이 순서를 따른다."""

    name: str = ""
    detail: str = ""


@dataclass
class TopicAnalysis:
    """analyze_topic 결과 — 주제를 구조화한 분석."""

    purpose: str = ""
    current_state: str = ""
    key_message: str = ""
    storyline: str = ""
    storyline_blocks: list[StorylineBlock] = field(default_factory=list)
    report_type: str = ""
    report_type_name: str = ""
    mode: str = "deep"                      # "summary" | "deep"
    recommended_pages: float = 0
    recommended_pages_reason: str = ""
    page_options: list[dict] = field(default_factory=list)


@dataclass
class GateResult:
    """정보 충실도/심층 게이트 판정 결과 (구조화 JSON)."""

    sufficient: bool = True
    questions: list[str] = field(default_factory=list)
    deep_targets: list[str] = field(default_factory=list)


@dataclass
class StructureProposal:
    """propose_structure 결과 — 구조 골격 + 추출된 미답 질문."""

    structure: str = ""
    questions: list[str] = field(default_factory=list)


@dataclass
class OutlineRequest:
    """build_outline 파라미터 묶음 (legacy 의 11개 위치인자 대체)."""

    topic: str
    loaded_style: str = ""
    extra: str = ""                         # 확정 구조 골격
    report_type: str = ""
    report_type_name: str = ""
    page_count: float = 0
    mode: str = "deep"
    storyline: str = ""
    storyline_blocks: str = ""
    unanswered: list[str] = field(default_factory=list)
    is_report: bool = False                 # 기존 문서 기반(report_based) 여부


@dataclass
class StyleProfile:
    """스타일 프로파일 — AgentCore/S3 에서 로드한 문체 서술."""

    text: str = ""
    source: str = ""                        # "agentcore" | "s3" | ""


@dataclass
class FlowState:
    """생성 도중 라이브 세션 상태 (비영속 — DB 저장 안 함).

    legacy ChatState 의 산발적 15개 state var 를 한 묶음으로 정리.
    """

    flow_stage: str = ""                    # "" | await_page_count | await_clarify
                                            #  | await_struct_info | await_outline_info | await_deep_info
    pending_topic: str = ""
    flow_analysis: str = ""
    proposed_structure: str = ""
    pending_questions: list[str] = field(default_factory=list)
    page_count: float = 0
    page_options: list[dict] = field(default_factory=list)
    recommended_pages: float = 0
    report_type: str = ""
    report_type_name: str = ""
    report_mode: str = "deep"
    report_storyline: str = ""
    report_storyline_blocks: str = ""
    struct_gate_total: int = 0
    gate_asked_questions: list[str] = field(default_factory=list)
    outline_reasked: bool = False
    deepdive_targets: str = ""
    user_mode: str = ""                     # "report_based" | "text_based" | ""
