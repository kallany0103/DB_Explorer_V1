import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QHBoxLayout, QFileDialog, QMessageBox, QLabel,
    QTabWidget, QWidget, QCheckBox, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QListWidget, QListWidgetItem, QSplitter
)
from PySide6.QtCore import Qt, QSize
import qtawesome as qta
import db


class CSVDataSourceDialog(QDialog):
    def __init__(self, parent=None, is_editing=False, type_id=None, group_id=None):
        super().__init__(parent)
        self.is_editing = is_editing
        self.type_id = type_id
        self.group_id = group_id
        self.inspected_tables = {}  # file_path -> inspected schema dict

        self.setWindowTitle("Edit CSV Data Source" if is_editing else "Add CSV Data Source")
        self.setFixedSize(720, 520)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._apply_styles()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # Header
        header_title = QLabel("CSV / Flat-File Data Source Wizard")
        header_title.setObjectName("dialogTitle")
        header_subtitle = QLabel("Auto-detect column headers and import CSV files into Unified Data Sources.")
        header_subtitle.setObjectName("dialogSubtitle")
        main_layout.addWidget(header_title)
        main_layout.addWidget(header_subtitle)

        # Tab Widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self._setup_general_tab()
        self._setup_schema_tab()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setObjectName("secondaryButton")
        self.test_btn.clicked.connect(self._test_connection)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Update Data Source" if is_editing else "Save Data Source")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._on_save)

        button_layout.addWidget(self.test_btn)
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(self.save_btn)
        main_layout.addLayout(button_layout)

    def _setup_general_tab(self):
        general_widget = QWidget()
        layout = QFormLayout(general_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(12)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., E-Commerce Reviews CSV")

        self.short_name_input = QLineEdit()
        self.short_name_input.setPlaceholderText("e.g. orders_csv, sales_data")

        # Mode: Single CSV file vs Directory
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Single CSV File", "Folder of CSV Files"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        # Path Picker
        path_box = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select CSV file or directory path...")
        self.path_input.textChanged.connect(self._on_path_changed)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_path)
        path_box.addWidget(self.path_input)
        path_box.addWidget(self.browse_btn)

        # Delimiter
        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems(["AUTO (Auto-Detect)", ", (Comma)", "\\t (Tab)", "; (Semicolon)", "| (Pipe)"])

        # Has Header
        self.header_checkbox = QCheckBox("First row contains column headers")
        self.header_checkbox.setChecked(True)

        layout.addRow("Connection Name:", self.name_input)
        layout.addRow("Data Source Short Name:", self.short_name_input)
        layout.addRow("Import Source Mode:", self.mode_combo)
        layout.addRow("File / Folder Path:", path_box)
        layout.addRow("CSV Delimiter:", self.delimiter_combo)
        layout.addRow("", self.header_checkbox)

        self.tabs.addTab(general_widget, "1. General Settings")

    def _setup_schema_tab(self):
        schema_widget = QWidget()
        layout = QVBoxLayout(schema_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top_bar = QHBoxLayout()
        self.scan_btn = QPushButton("Auto-Detect CSV Schema")
        self.scan_btn.setIcon(qta.icon("mdi.refresh", color="#0078d4"))
        self.scan_btn.clicked.connect(self._auto_detect_schema)

        self.table_count_label = QLabel("Detected Files: 0")
        self.table_count_label.setStyleSheet("color: #6b7280; font-weight: 600;")

        top_bar.addWidget(self.scan_btn)
        top_bar.addStretch()
        top_bar.addWidget(self.table_count_label)
        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: File list
        left_widget = QWidget()
        left_box = QVBoxLayout(left_widget)
        left_box.setContentsMargins(0, 0, 0, 0)
        left_box.addWidget(QLabel("CSV Files:"))

        self.file_list = QListWidget()
        self.file_list.itemSelectionChanged.connect(self._on_file_selected)
        left_box.addWidget(self.file_list)
        splitter.addWidget(left_widget)

        # Right: Column Schema Table
        right_widget = QWidget()
        right_box = QVBoxLayout(right_widget)
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.addWidget(QLabel("Auto-Detected Column Schema:"))

        self.col_table = QTableWidget(0, 3)
        self.col_table.setHorizontalHeaderLabels(["Column Name", "Inferred Type", "Original Header"])
        self.col_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.col_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        right_box.addWidget(self.col_table)
        splitter.addWidget(right_widget)

        splitter.setSizes([220, 440])
        layout.addWidget(splitter)

        self.tabs.addTab(schema_widget, "2. CSV Schema Preview")

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #f6f8fb; }
            QLabel#dialogTitle { font-size: 16px; font-weight: 600; color: #1f2937; }
            QLabel#dialogSubtitle { color: #6b7280; margin-bottom: 4px; }
            QLineEdit, QComboBox {
                min-height: 28px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 3px 8px;
                background: white;
            }
            QPushButton {
                min-height: 30px;
                padding: 4px 14px;
                border-radius: 6px;
                background-color: #eef1f6;
                border: 1px solid #c4c9d4;
            }
            QPushButton#primaryButton { background-color: #0078d4; color: white; font-weight: 600; }
            QTabWidget::pane { border: 1px solid #d1d5db; background: white; border-radius: 6px; }
        """)

    def _on_mode_changed(self, idx):
        self._auto_detect_schema()

    def _on_path_changed(self, text):
        if text.strip() and not self.name_input.text().strip():
            base = os.path.splitext(os.path.basename(text.strip()))[0]
            clean = "".join(c if c.isalnum() or c == '_' else '_' for c in base).strip('_').lower()
            self.name_input.setText(base.replace("_", " ").title())
            self.short_name_input.setText(f"{clean}_csv")

    def _browse_path(self):
        mode = self.mode_combo.currentText()
        if "Folder" in mode:
            path = QFileDialog.getExistingDirectory(self, "Select CSV Folder")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv);;All Files (*)")
        if path:
            self.path_input.setText(path)
            self._auto_detect_schema()

    def _get_delimiter_char(self):
        sel = self.delimiter_combo.currentText()
        if "\\t" in sel:
            return "\t"
        elif ";" in sel:
            return ";"
        elif "|" in sel:
            return "|"
        elif "," in sel:
            return ","
        return "AUTO"

    def _auto_detect_schema(self):
        path = self.path_input.text().strip()
        self.file_list.clear()
        self.col_table.setRowCount(0)
        self.inspected_tables.clear()

        if not path or not os.path.exists(path):
            self.table_count_label.setText("Detected Files: 0")
            return

        delimiter = self._get_delimiter_char()
        has_header = self.header_checkbox.isChecked()

        csv_files = []
        if os.path.isfile(path) and path.lower().endswith(".csv"):
            csv_files = [path]
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for f in files:
                    if f.lower().endswith(".csv"):
                        csv_files.append(os.path.join(root, f))

        self.table_count_label.setText(f"Detected Files: {len(csv_files)}")

        for f_path in csv_files:
            tbl_name = os.path.splitext(os.path.basename(f_path))[0]
            inspected = db.inspect_csv_schema(f_path, delimiter=delimiter, has_header=has_header)
            self.inspected_tables[f_path] = inspected

            item = QListWidgetItem(f"{tbl_name}.csv")
            item.setData(Qt.ItemDataRole.UserRole, f_path)
            item.setCheckState(Qt.CheckState.Checked)
            self.file_list.addItem(item)

        if self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)

    def _on_file_selected(self):
        curr = self.file_list.currentItem()
        if not curr:
            self.col_table.setRowCount(0)
            return

        f_path = curr.data(Qt.ItemDataRole.UserRole)
        inspected = self.inspected_tables.get(f_path, {})
        cols = inspected.get("columns", [])

        self.col_table.setRowCount(len(cols))
        for i, col in enumerate(cols):
            self.col_table.setItem(i, 0, QTableWidgetItem(col.get("name", "")))
            self.col_table.setItem(i, 1, QTableWidgetItem(col.get("type", "TEXT")))
            self.col_table.setItem(i, 2, QTableWidgetItem(col.get("original_name", "")))

    def _test_connection(self):
        path = self.path_input.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Validation", "Please select a valid CSV file or directory path.")
            return

        is_connected, msg, latency = db.test_data_source_connection({"source_type": "CSV", "file_path": path})
        if is_connected:
            QMessageBox.information(self, "Connection Test", f"🟢 CSV Data Source Accessible!\n\nDetails: {msg}")
        else:
            QMessageBox.critical(self, "Connection Error", f"🔴 Could not access CSV path:\n{msg}")

    def _on_save(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Validation", "Please enter a connection name.")
            return
        if not self.path_input.text().strip():
            QMessageBox.warning(self, "Validation", "Please select a CSV file or directory.")
            return

        self.accept()

    def getData(self):
        path = self.path_input.text().strip()
        delimiter = self._get_delimiter_char()
        has_header = self.header_checkbox.isChecked()

        selected_files = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                f_path = item.data(Qt.ItemDataRole.UserRole)
                tbl_name = os.path.splitext(os.path.basename(f_path))[0]
                inspected = self.inspected_tables.get(f_path, {})
                selected_files.append({
                    "file_path": f_path,
                    "table_name": tbl_name,
                    "delimiter": delimiter,
                    "has_header": has_header,
                    "columns": inspected.get("columns", [])
                })

        return {
            "name": self.name_input.text().strip(),
            "short_name": self.short_name_input.text().strip() or "csv_source",
            "file_path": path,
            "db_path": path,
            "delimiter": delimiter,
            "has_header": has_header,
            "csv_files": selected_files,
            "type_id": self.type_id,
            "group_id": self.group_id,
            "code": "CSV"
        }