import pathlib
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QHBoxLayout
)
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPainter, QBrush, QColor, QPainterPath, QMouseEvent

# Height (px) of the hand-drawn progress bar at the bottom of the splash.
_PROGRESS_BAR_H = 3


class SplashScreen(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setFixedSize(520, 320)
        qss_path = pathlib.Path(__file__).parent.parent / "ui" / "style.qss"
        if qss_path.exists():
            with open(qss_path, "r") as f:
                self.setStyleSheet(f.read())
        self._drag_offset: QPoint | None = None

        # Progress value stored as state; drawn in paintEvent inside the clip path
        self._progress: int = 0

        # Reserve bottom pixels for the hand-drawn progress bar
        _BOTTOM_PADDING = _PROGRESS_BAR_H + 20   # breathing room above bar

        # Main layout — leave bottom padding so labels don't overlap the bar
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, _BOTTOM_PADDING)
        main_layout.setSpacing(0)

        # ── Center block (title + subtitle) 
        center_layout = QVBoxLayout()
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel("Universal SQL Client")
        title_label.setObjectName("splashTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle_label = QLabel("Advanced Multi-Database IDE")
        subtitle_label.setObjectName("splashSubtitle")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        center_layout.addWidget(title_label)
        center_layout.addSpacing(8)
        center_layout.addWidget(subtitle_label)

        # ── Bottom info row (status / copyright / version) 
        bottom_layout = QVBoxLayout()
        bottom_layout.setContentsMargins(30, 0, 30, 10)

        self.status_label = QLabel("Starting up...")
        self.status_label.setObjectName("splashStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        info_row = QHBoxLayout()

        copyright_label = QLabel("© 2026 Universal Datafluent BD. All rights reserved.")
        copyright_label.setObjectName("splashCopyright")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        version_label = QLabel("v1.36")
        version_label.setObjectName("splashVersion")
        version_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        info_row.addWidget(copyright_label)
        info_row.addWidget(version_label)

        bottom_layout.addWidget(self.status_label)
        bottom_layout.addSpacing(5)
        bottom_layout.addLayout(info_row)

        # ── Assemble 
        main_layout.addStretch()
        main_layout.addLayout(center_layout)
        main_layout.addStretch()
        main_layout.addLayout(bottom_layout)

    # ── Drawing 

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        radius = 16

        # Rounded clip path — everything drawn here is clipped inside the corners
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, radius, radius)
        painter.setClipPath(path)

        # White background
        painter.fillPath(path, QBrush(QColor("#FFFFFF")))

        # Subtle colour blobs
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(66, 133, 244, 15))    # Blue
        painter.drawEllipse(350, -50, 300, 300)
        painter.setBrush(QColor(52, 168, 83, 10))     # Green
        painter.drawEllipse(450, 200, 150, 150)
        painter.setBrush(QColor(234, 67, 53, 10))     # Red
        painter.drawEllipse(-80, -80, 250, 250)
        painter.setBrush(QColor(250, 187, 5, 8))      # Yellow
        painter.drawEllipse(-50, 220, 200, 200)

        # ── Progress bar drawn inside the clip — never escapes rounded corners ──
        bar_h = _PROGRESS_BAR_H
        bar_y = h - bar_h

        # Track (light grey)
        painter.setBrush(QColor("#F1F3F4"))
        painter.drawRect(QRect(0, bar_y, w, bar_h))

        # Fill (Blue)
        filled_w = int(w * self._progress / 100)
        if filled_w > 0:
            painter.setBrush(QColor("#1A73E8"))
            painter.drawRect(QRect(0, bar_y, filled_w, bar_h))

        # Subtle border
        painter.setPen(QColor("#DADCE0"))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    # ── Public API 

    def set_status(self, message: str):
        self.status_label.setText(message)

    def set_progress(self, value: int):
        self._progress = max(0, min(100, value))
        self.update()   # trigger repaint

    def advance(self, message: str, value: int):
        self.set_status(message)
        self.set_progress(value)

    # ── Drag support 

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_offset = None
        super().mouseReleaseEvent(event)
