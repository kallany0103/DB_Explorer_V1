from __future__ import annotations

from typing import TYPE_CHECKING
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QDialog

if TYPE_CHECKING:
    from PySide6.QtGui import QScreen


def fit_dialog_to_screen(
    dialog: QDialog,
    ideal_width: int,
    ideal_height: int,
    min_width: int = 480,
    min_height: int = 320,
    max_screen_ratio_w: float = 0.92,
    max_screen_ratio_h: float = 0.88,
) -> None:
    """Dynamically size and center a dialog so it fits within the active screen viewport.

    Prevents dialog action buttons and title bars from getting pushed off-screen on
    laptops, scaled displays (125%/150%), and smaller monitors.
    """
    parent = dialog.parent()
    screen: QScreen | None = None
    if parent and hasattr(parent, "screen"):
        screen = parent.screen()
    elif parent and hasattr(parent, "window") and hasattr(parent.window(), "screen"):
        screen = parent.window().screen()

    if screen is None:
        screen = QApplication.primaryScreen()

    avail: QRect = screen.availableGeometry() if screen else QRect(0, 0, 1280, 720)

    max_w = max(min_width, int(avail.width() * max_screen_ratio_w))
    max_h = max(min_height, int(avail.height() * max_screen_ratio_h))

    target_w = min(ideal_width, max_w)
    target_h = min(ideal_height, max_h)

    safe_min_w = min(min_width, target_w)
    safe_min_h = min(min_height, target_h)
    dialog.setMinimumSize(safe_min_w, safe_min_h)
    dialog.setMaximumSize(avail.width(), avail.height())
    dialog.resize(target_w, target_h)

    center_x = avail.x() + (avail.width() - target_w) // 2
    center_y = avail.y() + (avail.height() - target_h) // 2

    clamped_x = max(avail.left() + 8, min(center_x, avail.right() - target_w - 8))
    clamped_y = max(avail.top() + 8, min(center_y, avail.bottom() - target_h - 8))
    dialog.move(clamped_x, clamped_y)
