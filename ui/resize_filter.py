# ui/resize_filter.py
"""Application-level event filter that adds edge/corner resize support to a
frameless QMainWindow by using Qt's built-in ``QWindow.startSystemResize``.

This is the officially recommended Qt approach (available since Qt 5.15):
the filter detects when the cursor enters a resize zone, sets the correct
resize cursor for visual feedback, and on left-button press delegates the
actual resize drag to the OS via ``startSystemResize`` — no ctypes or
Windows API required.

Install once during window init::

    from ui.resize_filter import ResizeFilter
    self._resize_filter = ResizeFilter(self)
    QApplication.instance().installEventFilter(self._resize_filter)
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QWidget


class ResizeFilter(QObject):
    """Event filter that provides frameless-window edge/corner resizing."""

    _BORDER: int = 6  # resize hit-zone width in logical pixels

    # Map Qt.Edges flag integer → cursor shape
    _EDGE_CURSORS: dict[int, Qt.CursorShape] = {
        Qt.Edge.LeftEdge.value:
            Qt.CursorShape.SizeHorCursor,
        Qt.Edge.RightEdge.value:
            Qt.CursorShape.SizeHorCursor,
        Qt.Edge.TopEdge.value:
            Qt.CursorShape.SizeVerCursor,
        Qt.Edge.BottomEdge.value:
            Qt.CursorShape.SizeVerCursor,
        (Qt.Edge.LeftEdge  | Qt.Edge.TopEdge).value:
            Qt.CursorShape.SizeFDiagCursor,
        (Qt.Edge.RightEdge | Qt.Edge.TopEdge).value:
            Qt.CursorShape.SizeBDiagCursor,
        (Qt.Edge.LeftEdge  | Qt.Edge.BottomEdge).value:
            Qt.CursorShape.SizeBDiagCursor,
        (Qt.Edge.RightEdge | Qt.Edge.BottomEdge).value:
            Qt.CursorShape.SizeFDiagCursor,
    }

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self._hovering_resize: bool = False

    # ------------------------------------------------------------------
    # Internal helpers

    def _resize_edges(self, global_pos) -> Qt.Edges:
        """Return which edges the cursor is hovering over (may be empty)."""
        win = self._window

        # Never resize while in our custom maximized state
        if getattr(win, "_is_maximized", False):
            return Qt.Edges()

        # Read title bar height; default to 30 px if unavailable
        title_bar_h: int = getattr(
            getattr(win, "_title_bar", None), "_TITLE_BAR_HEIGHT", 30
        )

        pos = win.mapFromGlobal(global_pos)
        px, py = pos.x(), pos.y()
        w, h = win.width(), win.height()
        b = self._BORDER
        cb = 16  # corner hit-zone is larger than edge hit-zone

        # Check corners first using the larger corner threshold
        if px < cb and py < cb:
            return Qt.Edge.LeftEdge | Qt.Edge.TopEdge
        if px > w - cb and py < cb:
            return Qt.Edge.RightEdge | Qt.Edge.TopEdge
        if px < cb and py > h - cb:
            return Qt.Edge.LeftEdge | Qt.Edge.BottomEdge
        if px > w - cb and py > h - cb:
            return Qt.Edge.RightEdge | Qt.Edge.BottomEdge

        # Check straight edges using the strict border threshold
        edges = Qt.Edges()
        if px < b:     edges |= Qt.Edge.LeftEdge
        if px > w - b: edges |= Qt.Edge.RightEdge
        if py < b:     edges |= Qt.Edge.TopEdge
        if py > h - b: edges |= Qt.Edge.BottomEdge
        return edges

    # ------------------------------------------------------------------
    # QObject.eventFilter

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        # Only handle events for widgets that belong to our window
        if not isinstance(obj, QWidget):
            return False
        if obj.window() is not self._window:
            return False

        etype = event.type()

        # ── Hover: set/clear resize cursor ──────────────────────────────
        if etype == QEvent.Type.MouseMove and not event.buttons():
            edges = self._resize_edges(event.globalPosition().toPoint())
            cursor = self._EDGE_CURSORS.get(edges.value)
            if cursor is not None:
                self._window.setCursor(cursor)
                self._hovering_resize = True
            elif self._hovering_resize:
                self._window.unsetCursor()
                self._hovering_resize = False
            return False  # do not consume — child still gets hover events

        # ── Press: kick off system resize if in a resize zone ───────────
        if etype == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                edges = self._resize_edges(event.globalPosition().toPoint())
                if edges:
                    handle = self._window.windowHandle()
                    if handle:
                        handle.startSystemResize(edges)
                    return True  # consume — prevent child from acting on it

        return False
