"""UI 상태 관리 - UIState.

Sidebar 접힘/펼침 등 UI 관련 상태를 담당.
"""

import reflex as rx


class UIState(rx.State):
    """UI 관련 상태를 관리하는 State 클래스."""

    sidebar_expanded: bool = True
    show_search: bool = False

    def toggle_sidebar(self) -> None:
        """Sidebar 접힘/펼침 상태를 토글한다."""
        self.sidebar_expanded = not self.sidebar_expanded

    def expand_sidebar(self) -> None:
        """Sidebar를 펼친다."""
        self.sidebar_expanded = True

    def collapse_sidebar(self) -> None:
        """Sidebar를 접는다."""
        self.sidebar_expanded = False

    def open_search(self) -> None:
        """채팅 검색을 활성화한다. 사이드바가 접혀 있으면 펼친다."""
        self.sidebar_expanded = True
        self.show_search = True

    def close_search(self) -> None:
        """채팅 검색을 비활성화한다."""
        self.show_search = False

    def toggle_search(self) -> None:
        """채팅 검색 표시 상태를 토글한다. 켤 때 사이드바도 펼친다."""
        if self.show_search:
            self.show_search = False
        else:
            self.sidebar_expanded = True
            self.show_search = True

    def noop(self) -> None:
        """아무 동작도 하지 않는 핸들러."""
