"""UI 상태 관리 - UIState.

Sidebar 토글, 고정/숨기기 등 UI 관련 상태를 담당한다.
"""

import reflex as rx


class UIState(rx.State):
    """UI 관련 상태를 관리하는 State 클래스."""

    sidebar_visible: bool = True
    sidebar_pinned: bool = True

    def toggle_sidebar(self) -> None:
        """Sidebar 표시 상태를 토글한다."""
        self.sidebar_visible = not self.sidebar_visible

    def pin_sidebar(self) -> None:
        """Sidebar를 고정한다."""
        self.sidebar_pinned = True
        self.sidebar_visible = True

    def unpin_sidebar(self) -> None:
        """Sidebar 고정을 해제한다."""
        self.sidebar_pinned = False

    def hide_sidebar(self) -> None:
        """Sidebar를 숨긴다."""
        self.sidebar_visible = False
        self.sidebar_pinned = False
