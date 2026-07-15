from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, 
    QLineEdit, QComboBox, QLabel, QPlainTextEdit, QMessageBox, 
    QHBoxLayout
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from ui.components import PrimaryButton, SecondaryButton

class CreatePolicyDialog(QDialog):
    def __init__(self, parent=None, schema_name="", table_name="", roles=None):
        super().__init__(parent)
        self.setWindowTitle("Create Policy")
        self.resize(600, 500)
        
        self.schema_name = schema_name
        self.table_name = table_name
        self.roles = roles or []
        
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        
        # Apply style from parent/manager if available
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
        title_lbl = QLabel("Create Policy")
        title_lbl.setObjectName("dialogTitle")
        subtitle_lbl = QLabel(f"Define a new Row Level Security policy for <b>{schema_name}.{table_name}</b>.")
        subtitle_lbl.setObjectName("dialogSubtitle")
        subtitle_lbl.setTextFormat(Qt.TextFormat.RichText)

        main_layout.addWidget(title_lbl)
        main_layout.addWidget(subtitle_lbl)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # --- Tab 1: General ---
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        gen_layout.setContentsMargins(15, 15, 15, 15)
        gen_layout.setSpacing(12)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("policy_name")
        
        self.command_combo = QComboBox()
        self.command_combo.addItems(["ALL", "SELECT", "INSERT", "UPDATE", "DELETE"])
        
        self.role_combo = QComboBox()
        self.role_combo.setEditable(True)
        self.role_combo.addItem("public")
        for role in self.roles:
            if role != "public":
                self.role_combo.addItem(role)
        
        gen_layout.addRow("Name:", self.name_input)
        gen_layout.addRow("Command:", self.command_combo)
        gen_layout.addRow("Role:", self.role_combo)
        
        self.tabs.addTab(self.general_tab, "General")

        # --- Tab 2: Using / With Check ---
        self.expr_tab = QWidget()
        expr_layout = QVBoxLayout(self.expr_tab)
        expr_layout.setContentsMargins(15, 15, 15, 15)
        
        using_lbl = QLabel("USING Expression (Applies to SELECT, UPDATE, DELETE):")
        using_lbl.setStyleSheet("color: #4b5563; font-weight: 500;")
        self.using_editor = QPlainTextEdit()
        self.using_editor.setPlaceholderText("e.g. current_user = owner_name")
        
        with_check_lbl = QLabel("WITH CHECK Expression (Applies to INSERT, UPDATE):")
        with_check_lbl.setStyleSheet("color: #4b5563; font-weight: 500;")
        self.with_check_editor = QPlainTextEdit()
        self.with_check_editor.setPlaceholderText("e.g. current_user = owner_name")
        
        font = QFont("Consolas", 10)
        if not font.fixedPitch():
            font = QFont("Courier New", 10)
        self.using_editor.setFont(font)
        self.with_check_editor.setFont(font)
        
        expr_layout.addWidget(using_lbl)
        expr_layout.addWidget(self.using_editor)
        expr_layout.addSpacing(10)
        expr_layout.addWidget(with_check_lbl)
        expr_layout.addWidget(self.with_check_editor)
        
        self.tabs.addTab(self.expr_tab, "Expressions")

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
            QMessageBox.warning(self, "Error", "Policy Name is required!")
            return
        self.accept()

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "command": self.command_combo.currentText(),
            "role": self.role_combo.currentText(),
            "using": self.using_editor.toPlainText().strip(),
            "with_check": self.with_check_editor.toPlainText().strip()
        }
