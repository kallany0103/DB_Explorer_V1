from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, 
    QLineEdit, QComboBox, QLabel, QPlainTextEdit, QDialogButtonBox, 
    QMessageBox, QHBoxLayout, QPushButton, QCheckBox
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

class CreateMaterializedViewDialog(QDialog):
    def __init__(self, parent=None, schemas=None, db_type="postgres"):
        super().__init__(parent)
        self.setWindowTitle("Create Materialized View")
        self.resize(700, 600)
        self.db_type = db_type
        
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        
        # Apply style from parent/manager
        if hasattr(parent, '_get_dialog_style'):
            self.setStyleSheet(parent._get_dialog_style() + """
                QTabWidget::pane { border: 1px solid #d1d5db; border-radius: 4px; top: -1px; background: white; }
                QTabBar::tab { background: #f3f4f6; border: 1px solid #d1d5db; padding: 6px 12px; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
                QTabBar::tab:selected { background: white; border-bottom-color: white; font-weight: 600; }
                QPlainTextEdit { border: 1px solid #d1d5db; border-radius: 4px; background: #fafafa; }
            """)

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 18)
        main_layout.setSpacing(14)

        # Header
        title_lbl = QLabel("Create Materialized View")
        title_lbl.setObjectName("dialogTitle")
        subtitle_lbl = QLabel(f"Define a new materialized view in the <b>{db_type}</b> database.")
        subtitle_lbl.setObjectName("dialogSubtitle")
        subtitle_lbl.setTextFormat(Qt.TextFormat.RichText)

        main_layout.addWidget(title_lbl)
        main_layout.addWidget(subtitle_lbl)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # --- Tab 1: General (Name, Schema) ---
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        gen_layout.setContentsMargins(15, 15, 15, 15)
        gen_layout.setSpacing(12)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("mview_name")
        self.schema_combo = QComboBox()
        self.schema_combo.setEditable(True)
        
        if schemas:
            self.schema_combo.addItems(schemas)
        else:
            self.schema_combo.addItem("public")
            
        self.with_no_data_check = QCheckBox("With No Data")
        self.with_no_data_check.setToolTip("Create the materialized view without populating it with data initially.")
            
        gen_layout.addRow("Name:", self.name_input)
        gen_layout.addRow("Schema:", self.schema_combo)
        gen_layout.addRow("", self.with_no_data_check)
        
        self.tabs.addTab(self.general_tab, "General")

        # --- Tab 2: Definition (SQL query) ---
        self.definition_tab = QWidget()
        def_layout = QVBoxLayout(self.definition_tab)
        def_layout.setContentsMargins(15, 15, 15, 15)
        
        def_lbl = QLabel("Definition (SQL SELECT statement):")
        def_lbl.setStyleSheet("color: #4b5563; font-weight: 500;")
        def_layout.addWidget(def_lbl)
        
        self.sql_editor = QPlainTextEdit()
        self.sql_editor.setPlaceholderText("SELECT * FROM some_table WHERE ...")
        # Set a monospace font for the editor
        font = QFont("Consolas", 10)
        if not font.fixedPitch():
            font = QFont("Courier New", 10)
        self.sql_editor.setFont(font)
        
        def_layout.addWidget(self.sql_editor)
        self.tabs.addTab(self.definition_tab, "Definition")

        # --- Footer Buttons ---
        footer_btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Create")
        self.save_btn.setObjectName("primaryButton")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondaryButton")
        
        footer_btn_layout.addStretch()
        footer_btn_layout.addWidget(self.cancel_btn)
        footer_btn_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(footer_btn_layout)
        
        self.save_btn.clicked.connect(self.validate_and_accept)
        self.cancel_btn.clicked.connect(self.reject)

    def validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Error", "Materialized View Name is required!")
            return
        if not self.sql_editor.toPlainText().strip():
            QMessageBox.warning(self, "Error", "SQL Definition is required!")
            return
        self.accept()

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "schema": self.schema_combo.currentText(),
            "definition": self.sql_editor.toPlainText().strip(),
            "with_no_data": self.with_no_data_check.isChecked()
        }
