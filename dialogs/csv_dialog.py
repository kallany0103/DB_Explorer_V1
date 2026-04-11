# dialogs/csv_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QPushButton, QHBoxLayout, QFileDialog, QMessageBox, QLabel, QComboBox, QInputDialog, QWidget, QApplication
)
from PySide6.QtCore import Qt
import db
from db.db_retrieval import get_groups_by_type

class CSVConnectionDialog(QDialog):
    def __init__(self, parent=None, conn_data=None, type_id=None, group_id=None):
        super().__init__(parent)
        self.type_id = type_id
        self.group_id = group_id
        self.setWindowTitle("Edit CSV Connection" if conn_data else "New CSV Connection")
        self.setFixedSize(560, 400) # Increased height
        self.setSizeGripEnabled(True)

        self._init_ui(conn_data)

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QDialog { background-color: #f6f8fb; }
            QLabel#dialogTitle { font-size: 16px; font-weight: 600; color: #1f2937; }
            QLabel#dialogSubtitle { color: #6b7280; margin-bottom: 8px; }
            QLineEdit, QComboBox {
                min-height: 30px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background: white;
                padding: 3px 8px;
                color: #1f2937;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #0078d4;
                background-color: #ffffff;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox {
                padding-right: 25px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #0078d4;
                background-color: #ffffff;
            }
            QPushButton {
                min-height: 32px;
                padding: 2px 14px;
                border: 1px solid #c4c9d4;
                background-color: #eef1f6;
                color: #1f2937;
                border-radius: 6px;
            }
            QPushButton#primaryButton { border: 1px solid #006cbe; background-color: #0078d4; color: #ffffff; font-weight: 600; }
            QPushButton#primaryButton:hover { background-color: #006cbe; }
            QPushButton#primaryButton:pressed { background-color: #005a9e; }
            """
        )

    def _init_ui(self, conn_data):
        self._apply_styles()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 18)
        main_layout.setSpacing(14)

        header_title = QLabel("CSV Connection")
        header_title.setObjectName("dialogTitle")
        header_subtitle = QLabel("Import and query CSV files as virtual tables.")
        header_subtitle.setObjectName("dialogSubtitle")
        main_layout.addWidget(header_title)
        main_layout.addWidget(header_subtitle)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(12)

        # Group Selection
        self.group_combo = QComboBox()
        self.new_group_btn = QPushButton("New Group")
        self.new_group_btn.setObjectName("secondaryButton")
        self.new_group_btn.setFixedWidth(110)
        self.new_group_btn.clicked.connect(self._create_new_group)
        
        group_layout = QHBoxLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.addWidget(self.group_combo)
        group_layout.addWidget(self.new_group_btn)

        if self.type_id:
            self._populate_groups()

        if self.group_id:
            index = self.group_combo.findData(self.group_id)
            if index >= 0:
                self.group_combo.setCurrentIndex(index)

        # Show group selection if editing (to allow transfer) OR if no group was pre-selected
        self.group_row_widget = QWidget()
        self.group_row_widget.setMinimumHeight(38)
        self.group_row_layout = QHBoxLayout(self.group_row_widget)
        self.group_row_layout.setContentsMargins(0, 2, 0, 2)
        self.group_row_layout.addLayout(group_layout)
        
        form_layout.addRow("Group:", self.group_row_widget)
        
        is_editing = conn_data is not None
        should_show_group = is_editing or not self.group_id
        if not should_show_group:
            self.group_row_widget.hide()
            label = form_layout.labelForField(self.group_row_widget)
            if label:
                label.hide()
            self.setFixedSize(560, 340) # Compact height when group is hidden

        # 1. Name Input
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Sales Data CSV")
        form_layout.addRow("Connection Name:", self.name_input)

        # 2. Short Name Input
        self.short_name_input = QLineEdit()
        self.short_name_input.setPlaceholderText("e.g., sales_csv")
        form_layout.addRow("Short Name:", self.short_name_input)

        # 3. Path Input with Browse Button
        path_container = QHBoxLayout()
        path_container.setSpacing(10)
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Path to folder containing CSV files")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_csv)
        path_container.addWidget(self.path_input)
        path_container.addWidget(browse_btn)
        form_layout.addRow("CSV Folder Path:", path_container)

        main_layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setObjectName("secondaryButton")
        self.test_btn.clicked.connect(self._test_connection)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        
        self.save_btn = QPushButton("Update" if conn_data else "Save")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._on_save)
        
        button_layout.addWidget(self.test_btn)
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(self.save_btn)
        main_layout.addLayout(button_layout)

        if conn_data:
            self.name_input.setText(conn_data.get("name", ""))
            self.short_name_input.setText(conn_data.get("short_name", ""))
            self.path_input.setText(conn_data.get("db_path", ""))

    def _test_connection(self):
        conn_data = self.getData()
        if not conn_data.get("db_path"):
            QMessageBox.warning(self, "Validation", "Please select a CSV file or folder.")
            return

        self.test_btn.setEnabled(False)
        self.test_btn.setText("Testing...")
        QApplication.processEvents()

        try:
            conn = db.create_csv_connection(conn_data)
            if conn:
                QMessageBox.information(self, "Success", "Connection successful!")
                conn.close()
            else:
                QMessageBox.critical(self, "Error", "Failed to connect to CSV. Please check the path.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection failed: {str(e)}")
        finally:
            self.test_btn.setEnabled(True)
            self.test_btn.setText("Test Connection")

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
                QMessageBox.critical(self, "Error", f"Failed to create group: {e}")

    def _browse_csv(self):
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select CSV Folder (Directory containing .csv files)"
        )
        if folder_path:
            self.path_input.setText(folder_path)

    def _on_save(self):
        if not self.name_input.text().strip():
             QMessageBox.warning(self, "Validation", "Please provide a connection name.")
             return
        if not self.path_input.text().strip():
             QMessageBox.warning(self, "Validation", "Please select a CSV file.")
             return
        if self.group_combo.currentIndex() == -1:
             QMessageBox.warning(self, "Missing Info", "Please select or create a group.")
             return
        self.accept()

    def getData(self):
        return {
            "name": self.name_input.text().strip(),
            "short_name": self.short_name_input.text().strip(), 
            "db_path": self.path_input.text().strip(),
            "connection_group_id": self.group_combo.currentData(),
            "code": "CSV"
        }