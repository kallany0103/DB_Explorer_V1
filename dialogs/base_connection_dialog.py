from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QFormLayout, QWidget, QComboBox, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt
from ui.components import PrimaryButton, SecondaryButton
import db
from db.db_retrieval import get_groups_by_type

class BaseConnectionDialog(QDialog):
    """
    Base class for all connection dialogs. Provides the standard window layout,
    header, button layout, and connection group selection logic.
    Subclasses should implement `setup_inputs()`, `test_connection_impl()`, 
    and `save_connection_impl()`.
    """
    def __init__(self, parent=None, conn_data=None, is_editing=False, type_id=None, group_id=None, title="Connection", subtitle="", fixed_size=None, min_size=None):
        super().__init__(parent)
        self.conn_data = conn_data
        self.type_id = type_id
        self.group_id = group_id

        # Determine if we are editing based on conn_data or the explicit flag
        self.is_editing = is_editing or (conn_data is not None)

        self.setWindowTitle(f"Edit {title}" if self.is_editing else f"New {title}")
        
        if fixed_size:
            self.setFixedSize(*fixed_size)
        elif min_size:
            self.setMinimumSize(*min_size)
            
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        # Main Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(22, 20, 22, 18)
        self.main_layout.setSpacing(14)

        # Header
        self.header_title = QLabel(f"{title} Connection" if "Connection" not in title else title)
        self.header_title.setObjectName("dialogTitle")
        self.header_subtitle = QLabel(subtitle)
        self.header_subtitle.setObjectName("dialogSubtitle")
        self.main_layout.addWidget(self.header_title)
        self.main_layout.addWidget(self.header_subtitle)

        # Form Layout
        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self.form.setHorizontalSpacing(18)
        self.form.setVerticalSpacing(12)

        # Group Selection
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
        self.group_row_widget.setMinimumHeight(38)
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
            # If we need to compact height when group is hidden, subclasses can handle it, 
            # or we can rely on layout.

        # Let subclasses add their specific inputs to self.form
        self.setup_inputs()

        self.main_layout.addLayout(self.form)
        self.main_layout.addStretch()

        # Buttons
        self.test_btn = SecondaryButton("Test Connection")
        self.test_btn.clicked.connect(self.testConnection)

        self.save_btn = PrimaryButton("Update" if self.is_editing else "Save")
        self.save_btn.clicked.connect(self.saveConnection)

        self.cancel_btn = SecondaryButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.test_btn)
        self.button_layout.addWidget(self.cancel_btn)
        self.button_layout.addWidget(self.save_btn)

        self.main_layout.addLayout(self.button_layout)

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
