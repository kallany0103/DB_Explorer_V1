import os
import pathlib
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar
)
from PySide6.QtCore import Qt, QCoreApplication, QPoint
from PySide6.QtGui import QPixmap, QPainter, QBrush, QColor, QPainterPath, QMouseEvent

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
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 40, 30, 20)
        layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
        
        # Load background image
        assets_dir = pathlib.Path(__file__).parent.parent / "assets"
        bg_path = assets_dir / "splash_bg.png"
        self.bg_pixmap = None
        if bg_path.exists():
            self.bg_pixmap = QPixmap(str(bg_path)).scaled(
                self.size(), 
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            
        # Title and Subtitle are drawn via paintEvent or added as labels
        title_label = QLabel("Universal SQL Client")
        title_label.setObjectName("splashTitle")
        
        subtitle_label = QLabel("Advanced Multi-Database IDE")
        subtitle_label.setObjectName("splashSubtitle")
        
        self.status_label = QLabel("Starting up...")
        self.status_label.setObjectName("splashStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setObjectName("splashProgressBar")
        
        version_label = QLabel("v1.35")
        version_label.setObjectName("splashVersion")
        version_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Layout arrangement
        layout.addStretch()
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addSpacing(30)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addSpacing(10)
        layout.addWidget(version_label)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Create rounded rect path
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        
        painter.setClipPath(path)
        
        if self.bg_pixmap:
            painter.drawPixmap(0, 0, self.bg_pixmap)
        else:
            painter.fillPath(path, QBrush(QColor("#1a1f2e")))
            
        # Border
        painter.setPen(QColor("#3d4460"))
        painter.drawPath(path)
        
    def set_status(self, message: str):
        self.status_label.setText(message)
        
    def set_progress(self, value: int):
        self.progress_bar.setValue(value)
        
    def advance(self, message: str, value: int):
        self.set_status(message)
        self.set_progress(value)

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
