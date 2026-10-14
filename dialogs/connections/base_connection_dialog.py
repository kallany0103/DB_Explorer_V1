from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QRect
from ui.components import PrimaryButton, SecondaryButton
import db
from db.db_retrieval import get_groups_by_type


class FitScrollArea(QScrollArea):
    """A scroll area that constrains its child widget width to the exact viewport width."""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.widget():
            target_w = max(100, self.viewport().width())
            self.widget().setFixedWidth(target_w)


class BaseConnectionDialog(QDialog):
    """
    Base class for all connection dialogs. Provides the standard window layout,
    header, scrollable form container, button layout, and connection group selection logic.
    Ensures dialogs are centered over the parent application and never clip off-screen.
    """
    def __init__(
        self,
        parent=None,
        conn_data=None,
        is_editing=False,
        type_id=None,
        group_id=None,
        title="Connection",
        subtitle="",
        fixed_size=None,
        min_size=None,
    ):
        # Resolve top-level parent window so the dialog centers and clamps to the application
        top_window = parent.window() if parent else None
        super().__init__(top_window or parent)

        self.conn_data = conn_data
        self.type_id = type_id
        self.group_id = group_id
        self._min_size_requested = min_size
        self._fixed_size_requested = fixed_size

        # Determine if we are editing based on conn_data or the explicit flag
        self.is_editing = is_editing or (conn_data is not None)

        self.setWindowTitle(f"Edit {title}" if self.is_editing else f"New {title}")
        self.setObjectName("baseConnectionDialog")

        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        # Main Layout (pins Header at top, Form in scroll area in middle, Buttons at bottom)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(22, 18, 22, 16)
        self.main_layout.setSpacing(10)

        # 1. Header (Fixed at top)
        self.header_title = QLabel(f"{title} Connection" if "Connection" not in title else title)
        self.header_title.setObjectName("dialogTitle")
        self.header_subtitle = QLabel(subtitle)
        self.header_subtitle.setObjectName("dialogSubtitle")
        self.main_layout.addWidget(self.header_title)
        self.main_layout.addWidget(self.header_subtitle)

        # 2. Scroll Area containing Form Layout (Flexible middle)
        self.scroll_area = FitScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setObjectName("dialogScrollArea")

        self.form_widget = QWidget()
        self.form_widget.setObjectName("dialogFormWidget")
        self.form = QFormLayout(self.form_widget)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self.form.setHorizontalSpacing(18)
        self.form.setVerticalSpacing(10)
        self.form.setContentsMargins(0, 4, 12, 4)

        # Group Selection (added as first row of self.form)
        self.group_combo = QComboBox()
        self.new_group_btn = SecondaryButton("New Group")
        self.new_group_btn.setFixedWidth(110)
        self.new_group_btn.clicked.connect(self._create_new_group)
        
        self.group_layout = QHBoxLayout()
        self.group_layout.setSpacing(10)
        self.group_layout.setContentsMargins(0, 0, 0, 0)
        self.group_layout.addWidget(self.group_combo)
        self.group_layout.addWidget(self.new_group_btn)

        if self.type_id:
            self._populate_groups()
            
        if self.group_id:
            index = self.group_combo.findData(self.group_id)
            if index >= 0:
                self.group_combo.setCurrentIndex(index)

        self.group_row_widget = QWidget()
        self.group_row_widget.setMinimumHeight(36)
        self.group_row_layout = QHBoxLayout(self.group_row_widget)
        self.group_row_layout.setContentsMargins(0, 2, 0, 2)
        self.group_row_layout.addLayout(self.group_layout)
        
        self.form.addRow("Group:", self.group_row_widget)
        
        should_show_group = self.is_editing or not self.group_id
        if not should_show_group:
            self.group_row_widget.hide()
            label = self.form.labelForField(self.group_row_widget)
            if label:
                label.hide()

        # Let subclasses add their specific inputs to self.form
        self.setup_inputs()

        self.scroll_area.setWidget(self.form_widget)
        self.main_layout.addWidget(self.scroll_area, 1)

        # 3. Action Buttons (Fixed at bottom)
        self.test_btn = SecondaryButton("Test Connection")
        self.test_btn.setFixedWidth(130)
        self.test_btn.clicked.connect(self.testConnection)

        self.cancel_btn = SecondaryButton("Cancel")
        self.cancel_btn.setFixedWidth(84)
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = PrimaryButton("Update" if self.is_editing else "Save")
        self.save_btn.setFixedWidth(84)
        self.save_btn.clicked.connect(self.saveConnection)

        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.test_btn)
        self.button_layout.addWidget(self.cancel_btn)
        self.button_layout.addWidget(self.save_btn)

        self.main_layout.addLayout(self.button_layout)

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_inside_parent_and_screen()

    def _ensure_inside_parent_and_screen(self):
        # 1. Determine screen available geometry
        top_win = self.parentWidget().window() if self.parentWidget() else None
        screen = None
        if top_win and top_win.screen():
            screen = top_win.screen()
        elif self.screen():
            screen = self.screen()
        else:
            screen = QApplication.primaryScreen()

        screen_rect = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        # 2. Determine target boundary (parent application window if valid, else screen)
        if (
            top_win
            and top_win.isVisible()
            and not top_win.isMinimized()
            and top_win.width() > 300
            and top_win.height() > 300
        ):
            target_rect = top_win.geometry()
        else:
            target_rect = screen_rect

        # 3. Calculate max allowed dimensions to never exceed parent or screen
        max_allowed_w = max(360, min(target_rect.width() - 24, screen_rect.width() - 24))
        max_allowed_h = max(300, min(target_rect.height() - 36, screen_rect.height() - 36))

        # 4. Handle fixed or min size requests within safe bounds
        if self._fixed_size_requested:
            fw = min(self._fixed_size_requested[0], max_allowed_w)
            fh = min(self._fixed_size_requested[1], max_allowed_h)
            self.setFixedSize(fw, fh)
        else:
            min_w = 480
            min_h = 320
            if self._min_size_requested:
                min_w = min(self._min_size_requested[0], max_allowed_w)
                min_h = min(self._min_size_requested[1], max_allowed_h)
            self.setMinimumSize(min_w, min_h)
            self.setMaximumSize(max_allowed_w, max_allowed_h)

            # Compute ideal content height
            content_h = (
                self.header_title.sizeHint().height()
                + self.header_subtitle.sizeHint().height()
                + self.form_widget.sizeHint().height()
                + self.button_layout.sizeHint().height()
                + 50
            )
            ideal_w = min(max(self.width(), 620), max_allowed_w)
            ideal_h = min(max(content_h, min_h), max_allowed_h)
            self.resize(ideal_w, ideal_h)

        # 5. Calculate centered position relative to target_rect
        center_x = target_rect.x() + (target_rect.width() - self.width()) // 2
        center_y = target_rect.y() + (target_rect.height() - self.height()) // 2

        # 6. Strictly clamp within BOTH target_rect and screen_rect
        clamp_left = max(screen_rect.left() + 8, target_rect.left() + 8)
        clamp_right = min(screen_rect.right() - self.width() - 8, target_rect.right() - self.width() - 8)
        clamp_top = max(screen_rect.top() + 8, target_rect.top() + 8)
        clamp_bottom = min(screen_rect.bottom() - self.height() - 8, target_rect.bottom() - self.height() - 8)

        if clamp_right < clamp_left:
            final_x = clamp_left
        else:
            final_x = max(clamp_left, min(center_x, clamp_right))

        if clamp_bottom < clamp_top:
            final_y = clamp_top
        else:
            final_y = max(clamp_top, min(center_y, clamp_bottom))

        self.move(final_x, final_y)

    def _populate_groups(self):
        self.group_combo.clear()
        groups = get_groups_by_type(self.type_id)
        for g in groups:
            self.group_combo.addItem(g["name"], g["id"])
            
    def _create_new_group(self):
        name, ok = QInputDialog.getText(self, "New Group", "Enter group name:")
        if ok and name.strip():
            try:
                db.add_connection_group(name.strip(), self.type_id)
                self._populate_groups()
                index = self.group_combo.findText(name.strip())
                if index >= 0:
                    self.group_combo.setCurrentIndex(index)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create group:\n{e}")

    # Subclass hooks
    def setup_inputs(self):
        pass

    def testConnection(self):
        self.test_connection_impl()

    def saveConnection(self):
        if self.group_combo.currentIndex() == -1:
            QMessageBox.warning(self, "Missing Info", "Please select or create a group.")
            return
        self.save_connection_impl()

    def test_connection_impl(self):
        pass

    def save_connection_impl(self):
        pass
