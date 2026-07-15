from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, 
    QLineEdit, QComboBox, QLabel, QPlainTextEdit, QMessageBox, 
    QHBoxLayout, QCheckBox
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from ui.components import PrimaryButton, SecondaryButton

class CreateTriggerFunctionDialog(QDialog):
    def __init__(self, parent=None, schemas=None, current_user="postgres", db_type="postgres"):
        super().__init__(parent)
        self.setWindowTitle(f"Create Trigger Function ({db_type.capitalize()})")
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
                QTabBar::tab { background: #f3f4f6; border: 1px solid #d1d5db; padding: 6px 12px; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; color: #4b5563; }
                QTabBar::tab:selected { background: white; border-bottom-color: white; font-weight: 600; color: #111827; }
                QPlainTextEdit { border: 1px solid #d1d5db; border-radius: 4px; background: #fafafa; }
            """)

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 18)
        main_layout.setSpacing(14)

        # Header
        title_lbl = QLabel("Create Trigger Function")
        title_lbl.setObjectName("dialogTitle")
        subtitle_lbl = QLabel(f"Define a new trigger function in the <b>{db_type}</b> database.")
        subtitle_lbl.setObjectName("dialogSubtitle")
        subtitle_lbl.setTextFormat(Qt.TextFormat.RichText)

        main_layout.addWidget(title_lbl)
        main_layout.addWidget(subtitle_lbl)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # --- Tab 1: General (Name, Schema, Language) ---
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        gen_layout.setContentsMargins(15, 15, 15, 15)
        gen_layout.setSpacing(12)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("trigger_function_name")
        self.schema_combo = QComboBox()
        self.schema_combo.setEditable(True)
        self.language_combo = QComboBox()
        
        if db_type == 'postgres':
            self.language_combo.addItems(["plpgsql", "plpython3u", "plperl", "pltcl"])
        else:
            self.language_combo.addItems(["sql"])
        
        if schemas:
            self.schema_combo.addItems(schemas)
        else:
            self.schema_combo.addItem("public" if db_type == 'postgres' else "main")
            
        gen_layout.addRow("Name:", self.name_input)
        if self.db_type == 'postgres':
            gen_layout.addRow("Schema:", self.schema_combo)
        gen_layout.addRow("Language:", self.language_combo)
        
        self.tabs.addTab(self.general_tab, "General")

        # --- Tab 2: Definition (Function Body) ---
        self.definition_tab = QWidget()
        def_layout = QVBoxLayout(self.definition_tab)
        def_layout.setContentsMargins(15, 15, 15, 15)
        
        def_lbl = QLabel("Trigger Function Body:")
        def_lbl.setStyleSheet("color: #4b5563; font-weight: 500;")
        def_layout.addWidget(def_lbl)
        
        self.sql_editor = QPlainTextEdit()
        self.sql_editor.setPlaceholderText("BEGIN\n    -- Your trigger logic here\n    -- Use NEW and OLD to access row data\n    IF TG_OP = 'INSERT' THEN\n        -- Handle INSERT\n    ELSIF TG_OP = 'UPDATE' THEN\n        -- Handle UPDATE\n    ELSIF TG_OP = 'DELETE' THEN\n        -- Handle DELETE\n    END IF;\n    RETURN NEW;\nEND;")
        font = QFont("Consolas", 10)
        if not font.fixedPitch():
            font = QFont("Courier New", 10)
        self.sql_editor.setFont(font)
        
        def_layout.addWidget(self.sql_editor)
        self.tabs.addTab(self.definition_tab, "Definition")

        # --- Tab 3: Options ---
        self.options_tab = QWidget()
        opt_layout = QFormLayout(self.options_tab)
        opt_layout.setContentsMargins(15, 15, 15, 15)
        opt_layout.setSpacing(12)
        
        self.immutable_check = QCheckBox("IMMUTABLE")
        self.stable_check = QCheckBox("STABLE")
        self.volatile_check = QCheckBox("VOLATILE")
        self.volatile_check.setChecked(True)
        self.leakproof_check = QCheckBox("LEAKPROOF")
        self.security_definer_check = QCheckBox("SECURITY DEFINER")
        
        opt_layout.addRow("Volatility:", self.immutable_check)
        opt_layout.addRow("", self.stable_check)
        opt_layout.addRow("", self.volatile_check)
        opt_layout.addRow("Security:", self.leakproof_check)
        opt_layout.addRow("", self.security_definer_check)
        
        self.tabs.addTab(self.options_tab, "Options")

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
            QMessageBox.warning(self, "Error", "Trigger Function Name is required!")
            return
        if not self.sql_editor.toPlainText().strip():
            QMessageBox.warning(self, "Error", "Function Body is required!")
            return
        self.accept()

    def get_data(self):
        volatility = "VOLATILE"
        if self.immutable_check.isChecked():
            volatility = "IMMUTABLE"
        elif self.stable_check.isChecked():
            volatility = "STABLE"
        
        return {
            "name": self.name_input.text().strip(),
            "schema": self.schema_combo.currentText(),
            "language": self.language_combo.currentText(),
            "body": self.sql_editor.toPlainText().strip(),
            "volatility": volatility,
            "leakproof": self.leakproof_check.isChecked(),
            "security_definer": self.security_definer_check.isChecked()
        }
