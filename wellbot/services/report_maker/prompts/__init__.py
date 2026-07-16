"""report_maker 프롬프트 상수 모음 (legacy config.py 원문 분리)."""

from .outline_rules import OUTLINE_GENERATION_RULES
from .structure_rules import (
    PAGE_STRUCTURE_GUIDE,
    REPORT_STRUCTURES,
    STRUCTURE_HEADING_RULES,
)
from .table_rules import TABLE_READING_RULES

__all__ = [
    "OUTLINE_GENERATION_RULES",
    "STRUCTURE_HEADING_RULES",
    "TABLE_READING_RULES",
    "REPORT_STRUCTURES",
    "PAGE_STRUCTURE_GUIDE",
]
