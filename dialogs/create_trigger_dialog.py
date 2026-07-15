from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, 
    QLineEdit, QComboBox, QLabel, QPlainTextEdit, QMessageBox, 
    QHBoxLayout, QCheckBox
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from ui.components import PrimaryButton, SecondaryButton

class CreateTriggerDialog(QDialog):
    def __init__(self, parent=None, schemas=None, tables=None, db_type="postgres"):
        super().__init__(parent)
        self.setWindowTitle("Create Trigger")
        self.resize(700, 650)
        self.db_type = db_type
        self.tables = tables or []
        
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
                QTabBar::tab { background: #f3f4f6; border: 1px solid #d1d5db; padding: 6px 12px; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; color: #4b5563; }
                QTabBar::tab:selected { background: white; border-bottom-color: white; font-weight: 600; color: #111827; }
                QPlainTextEdit { border: 1px solid #d1d5db; border-radius: 4px; background: #fafafa; }
            """)

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 18)
        main_layout.setSpacing(14)

        # Header
        title_lbl = QLabel("Create Trigger")
        title_lbl.setObjectName("dialogTitle")
        subtitle_lbl = QLabel(f"Define a new trigger in the <b>{db_type}</b> database.")
        subtitle_lbl.setObjectName("dialogSubtitle")
        subtitle_lbl.setTextFormat(Qt.TextFormat.RichText)

        main_layout.addWidget(title_lbl)
        main_layout.addWidget(subtitle_lbl)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # --- Tab 1: General (Name, Schema, Table) ---
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        gen_layout.setContentsMargins(15, 15, 15, 15)
        gen_layout.setSpacing(12)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("trigger_name")
        self.schema_combo = QComboBox()
        self.schema_combo.setEditable(True)
        self.table_combo = QComboBox()
        self.table_combo.setEditable(True)
        
        if schemas:
            self.schema_combo.addItems(schemas)
        else:
            self.schema_combo.addItem("public")
            
        if self.tables:
            self.table_combo.addItems(self.tables)
            
        gen_layout.addRow("Name:", self.name_input)
        gen_layout.addRow("Schema:", self.schema_combo)
        gen_layout.addRow("Table:", self.table_combo)
        
        self.tabs.addTab(self.general_tab, "General")

        # --- Tab 2: Trigger Details (Timing, Event, Function) ---
        self.details_tab = QWidget()
        details_layout = QFormLayout(self.details_tab)
        details_layout.setContentsMargins(15, 15, 15, 15)
        details_layout.setSpacing(12)
        
        self.timing_combo = QComboBox()
        self.timing_combo.addItems(["BEFORE", "AFTER", "INSTEAD OF"])
        
        self.event_combo = QComboBox()
        self.event_combo.addItems(["INSERT", "UPDATE", "DELETE", "TRUNCATE"])
        
        self.function_input = QLineEdit()
        self.function_input.setPlaceholderText("schema.function_name")
        
        self.when_condition = QPlainTextEdit()
        self.when_condition.setPlaceholderText("WHEN (condition)")
        self.when_condition.setMaximumHeight(80)
        
        details_layout.addRow("Timing:", self.timing_combo)
        details_layout.addRow("Event:", self.event_combo)
        details_layout.addRow("Function:", self.function_input)
        details_layout.addRow("When Condition:", self.when_condition)
        
        self.tabs.addTab(self.details_tab, "Trigger Details")

        # --- Tab 3: Definition (Custom SQL) ---
        self.definition_tab = QWidget()
        def_layout = QVBoxLayout(self.definition_tab)
        def_layout.setContentsMargins(15, 15, 15, 15)
        
        def_lbl = QLabel("Custom SQL Definition (optional):")
        def_lbl.setStyleSheet("color: #4b5563; font-weight: 500;")
        def_layout.addWidget(def_lbl)
        
        self.sql_editor = QPlainTextEdit()
        self.sql_editor.setPlaceholderText("-- Leave empty to auto-generate from trigger details")
        # Set a monospace font for the editor
        font = QFont("Consolas", 10)
        if not font.fixedPitch():
            font = QFont("Courier New", 10)
        self.sql_editor.setFont(font)
        
        def_layout.addWidget(self.sql_editor)
        self.tabs.addTab(self.definition_tab, "Definition")

        # --- Footer Buttons ---
        footer_btn_layout = QHBoxLayout()
        self.save_btn = PrimaryButton("Create")
        self.cancel_btn = SecondaryButton("Cancel")
        
        footer_btn_layout.addStretch()
        footer_btn_layout.addWidget(self.cancel_btn)
        footer_btn_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(footer_btn_layout)
        
        self.save_btn.clicked.connect(self.validate_and_accept)
        self.cancel_btn.clicked.connect(self.reject)

    def validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Error", "Trigger Name is required!")
            return
        if not self.table_combo.currentText().strip():
            QMessageBox.warning(self, "Error", "Table Name is required!")
            return
        if not self.function_input.text().strip() and not self.sql_editor.toPlainText().strip():
            QMessageBox.warning(self, "Error", "Either Function Name or Custom SQL Definition is required!")
            return
        self.accept()

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "schema": self.schema_combo.currentText(),
            "table": self.table_combo.currentText(),
            "timing": self.timing_combo.currentText(),
            "event": self.event_combo.currentText(),
            "function": self.function_input.text().strip(),
            "when_condition": self.when_condition.toPlainText().strip(),
            "custom_sql": self.sql_editor.toPlainText().strip()
        }
