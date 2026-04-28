"""UI 상태 관리 - UIState.

Sidebar 접힘/펼침 등 UI 관련 상태를 담당.
"""

import reflex as rx


class UIState(rx.State):
    """UI 관련 상태를 관리하는 State 클래스."""

    sidebar_expanded: bool = True

    def toggle_sidebar(self) -> None:
        """Sidebar 접힘/펼침 상태를 토글한다."""
        self.sidebar_expanded = not self.sidebar_expanded

    def expand_sidebar(self) -> None:
        """Sidebar를 펼친다."""
        self.sidebar_expanded = True

    def collapse_sidebar(self) -> None:
        """Sidebar를 접는다."""
        self.sidebar_expanded = False

    def noop(self) -> None:
        """아무 동작도 하지 않는 핸들러."""
