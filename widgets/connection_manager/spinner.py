"""ConnectionSpinner - animated loading indicator for QStandardItem icons.

Fix history:
  v1 - qta options rotated=angle          -> all frames identical, blink only
  v2 - QPainter rotation at 16 px         -> correct frames but jagged pixels
  v3 - supersampled rotation (4x)         -> smoother but still blocky on HiDPI
  v4 - DPR-aware pixmaps                  -> clean but only for primary screen
  v5 - multi-resolution QIcon frames      -> correct on every screen, every DPR,
                                             even when window moves monitors
"""

import qtawesome as qta
from PySide6.QtCore import Qt, QSize, QTimer, QObject
from PySide6.QtGui import QIcon, QPainter, QPixmap, QTransform

_FRAME_COUNT   = 12         # 360 / 12 = 30 degrees per step
_INTERVAL_MS   = 60         # ~16 fps
_SPINNER_COLOR = "#0078d4"
_ICON_SIZE     = 16         # logical icon size in pixels
_SUPERSAMPLE   = 4          # render at Nx before scaling down (anti-aliasing)

# Qt will pick the best pixmap from this list for the current screen.
# Covers: standard (1x), Windows 125%/150% (1.25/1.5x), Retina (2x), 4K (3x).
_DPRS = [1.0, 1.25, 1.5, 2.0, 3.0]


def _make_pixmap_for_dpr(base_icon: QIcon, angle: float,
                          logical_size: int, dpr: float,
                          supersample: int) -> QPixmap:
    """Render *base_icon* rotated by *angle* degrees at the given *dpr*.

    Pipeline
    --------
    1. Render the glyph at  logical_size x dpr x supersample  physical pixels
       so the font renderer produces a smooth, fully-formed glyph.
    2. Rotate at that large canvas - aliasing is negligible at high resolution.
    3. Bicubic-downsample back to  logical_size x dpr  physical pixels.
    4. Tag with setDevicePixelRatio(dpr) so Qt maps it to the correct logical
       size when painting on screen.
    """
    phys_size = int(logical_size * dpr)          # e.g. 32 on a 2x screen
    hi_size   = phys_size * supersample          # e.g. 128 - the render canvas

    # Ask qtawesome to rasterise the font glyph at the large canvas size.
    base_pixmap = base_icon.pixmap(QSize(hi_size, hi_size))

    # Rotate into a transparent canvas of the same large size.
    hi_dst = QPixmap(hi_size, hi_size)
    hi_dst.fill(Qt.GlobalColor.transparent)

    cx = hi_size / 2.0
    painter = QPainter(hi_dst)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    t = QTransform()
    t.translate(cx, cx)
    t.rotate(angle)
    t.translate(-cx, -cx)
    painter.setTransform(t)
    painter.drawPixmap(0, 0, base_pixmap)
    painter.end()

    # Downsample - this bicubic pass acts as the final anti-aliasing step.
    lo_dst = hi_dst.scaled(
        QSize(phys_size, phys_size),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

    # Tell Qt: these physical pixels represent a logical_size x logical_size icon.
    lo_dst.setDevicePixelRatio(dpr)
    return lo_dst


def _build_rotated_frames(base_icon: QIcon, count: int,
                           logical_size: int, supersample: int) -> list:
    """Return *count* multi-resolution QIcons (one per rotation step).

    Each QIcon holds one pixmap per DPR in _DPRS.  Qt automatically selects
    the best pixmap for the screen the widget is currently displayed on,
    including after the window is dragged to a different monitor.
    """
    step   = 360.0 / count
    frames = []

    for i in range(count):
        angle = i * step
        icon  = QIcon()

        for dpr in _DPRS:
            pixmap = _make_pixmap_for_dpr(
                base_icon, angle, logical_size, dpr, supersample
            )
            icon.addPixmap(pixmap)

        frames.append(icon)

    return frames


class ConnectionSpinner(QObject):
    """Animates a single QStandardItem's icon while a connection is loading.

    Each animation frame is a multi-resolution QIcon, so the spinner renders
    crisply on standard monitors, HiDPI/Retina displays, and mixed-DPR
    multi-monitor setups - with no manual DPR tracking required.

    Usage::

        # __init__
        self._spinner = ConnectionSpinner(self)

        # on connection click
        self._spinner.start(item)   # item = the clicked QStandardItem

        # when loading finishes or errors
        self._spinner.stop()        # restores original icon automatically
    """

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)

        base = qta.icon("fa5s.circle-notch", color=_SPINNER_COLOR)
        self._frames = _build_rotated_frames(
            base, _FRAME_COUNT, _ICON_SIZE, _SUPERSAMPLE
        )

        self._timer = QTimer(self)
        self._timer.setInterval(_INTERVAL_MS)
        self._timer.timeout.connect(self._advance)

        self._item       = None
        self._saved_icon = None
        self._frame_idx  = 0
        self._running    = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, item) -> None:
        """Attach the spinner to *item* and start animating."""
        if self._timer.isActive():
            self._stop_internal(restore=True)
        if item is None:
            return
        self._item       = item
        self._saved_icon = item.icon()
        self._frame_idx  = 0
        self._running    = True
        self._item.setIcon(self._frames[0])
        self._timer.start()

    def stop(self) -> None:
        """Stop animation and restore *item*'s original icon."""
        self._stop_internal(restore=True)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _stop_internal(self, restore: bool) -> None:
        self._running = False
        self._timer.stop()
        item = self._item
        saved_icon = self._saved_icon
        self._item = None
        self._saved_icon = None
        self._frame_idx = 0
        if restore and item is not None and saved_icon is not None:
            item.setIcon(saved_icon)

    def _advance(self) -> None:
        if not self._running or self._item is None:
            self._timer.stop()
            return
        self._frame_idx = (self._frame_idx + 1) % _FRAME_COUNT
        self._item.setIcon(self._frames[self._frame_idx])
