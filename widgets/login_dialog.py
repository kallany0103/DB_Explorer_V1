import pathlib
import qtawesome as qta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QToolButton, QMessageBox
)
from PySide6.QtCore import Qt, QPoint, QSize
from PySide6.QtGui import (
    QPainter, QBrush, QColor, QPainterPath,
    QMouseEvent, QPixmap
)


class LoginDialog(QDialog):
    """Username-and-password sign-in dialog."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.result_user: dict | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 430)

        qss_path = pathlib.Path(__file__).parent.parent / "ui" / "style.qss"
        if qss_path.exists():
            with open(qss_path, "r") as f:
                self.setStyleSheet(f.read())

        self._drag_offset: QPoint | None = None
        self._build_ui()

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 30)
        root.setSpacing(0)

        # ── App identity ─────────────────────────────────────────────────────
        identity_layout = QHBoxLayout()
        identity_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl = QLabel()
        icon_lbl.setObjectName("loginAppIcon")
        icon_pix_path = pathlib.Path(__file__).parent.parent / "assets" / "sql_icon.png"
        if icon_pix_path.exists():
            icon_lbl.setPixmap(
                QPixmap(str(icon_pix_path)).scaled(
                    28, 28,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
        app_name = QLabel("Universal SQL Client")
        app_name.setObjectName("loginAppName")
        identity_layout.addWidget(icon_lbl)
        identity_layout.addSpacing(8)
        identity_layout.addWidget(app_name)
        root.addLayout(identity_layout)
        root.addSpacing(28)

        # ── Heading ──────────────────────────────────────────────────────────
        heading = QLabel("Sign in")
        heading.setObjectName("loginHeading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(heading)
        root.addSpacing(8)

        sub = QLabel("Use your email and password to continue")
        sub.setObjectName("loginSubheading")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(sub)
        root.addSpacing(24)

        # ── Email field ──────────────────────────────────────────────────────
        self.email_input = QLineEdit()
        self.email_input.setObjectName("loginInput")
        self.email_input.setPlaceholderText("Email or username")
        self.email_input.setMinimumHeight(44)
        root.addWidget(self.email_input)
        root.addSpacing(14)

        # ── Password field ───────────────────────────────────────────────────
        pwd_row = QHBoxLayout()
        pwd_row.setSpacing(0)
        self.pwd_input = QLineEdit()
        self.pwd_input.setObjectName("loginInput")
        self.pwd_input.setPlaceholderText("Password")
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setMinimumHeight(44)
        self._toggle_eye = QToolButton()
        self._toggle_eye.setObjectName("loginEyeBtn")
        self._toggle_eye.setIcon(qta.icon("fa5s.eye", color="#9AA0A6"))
        self._toggle_eye.setIconSize(QSize(16, 16))
        self._toggle_eye.setFixedSize(40, 44)
        self._toggle_eye.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_eye.clicked.connect(self._toggle_password_visibility)
        pwd_row.addWidget(self.pwd_input)
        pwd_row.addWidget(self._toggle_eye)
        root.addLayout(pwd_row)
        root.addSpacing(22)

        # ── Sign In button ───────────────────────────────────────────────────
        self.signin_btn = QPushButton("Sign in")
        self.signin_btn.setObjectName("loginPrimaryBtn")
        self.signin_btn.setMinimumHeight(42)
        self.signin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.signin_btn.clicked.connect(self._on_signin)
        root.addWidget(self.signin_btn)
        root.addSpacing(16)
        root.addStretch()

        # ── Skip link ─────────────────────────────────────────────────────────
        skip_btn = QPushButton("Continue without login  →")
        skip_btn.setObjectName("loginSkipBtn")
        skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        skip_btn.clicked.connect(self._on_skip)
        skip_btn.setFlat(True)
        root.addWidget(skip_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _toggle_password_visibility(self) -> None:
        if self.pwd_input.echoMode() == QLineEdit.EchoMode.Password:
            self.pwd_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._toggle_eye.setIcon(qta.icon("fa5s.eye-slash", color="#9AA0A6"))
        else:
            self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._toggle_eye.setIcon(qta.icon("fa5s.eye", color="#9AA0A6"))

    def _on_signin(self) -> None:
        QMessageBox.information(
            self,
            "Not yet available",
            "Account login is coming soon.\n\nPlease use 'Continue without login' for now.",
        )

    def _on_skip(self) -> None:
        """Proceed with no authentication — app behaves exactly as before."""
        self.result_user = None
        self.accept()

    # ── Background painting ───────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 16, 16)
        painter.setClipPath(path)

        # White card background
        painter.fillPath(path, QBrush(QColor("#FFFFFF")))

        # Subtle Google-brand colour blobs
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(66, 133, 244, 12))   # Blue — top right
        painter.drawEllipse(280, -60, 260, 260)
        painter.setBrush(QColor(234, 67, 53, 8))     # Red — top left
        painter.drawEllipse(-60, -60, 180, 180)
        painter.setBrush(QColor(52, 168, 83, 8))     # Green — bottom right
        painter.drawEllipse(320, 380, 160, 160)
        painter.setBrush(QColor(250, 187, 5, 6))     # Yellow — bottom left
        painter.drawEllipse(-40, 380, 160, 160)

        # Border
        painter.setPen(QColor("#DADCE0"))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    # ── Drag support ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)
