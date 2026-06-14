from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, 
    QLineEdit, QComboBox, QLabel, QMessageBox, 
    QHBoxLayout, QPushButton, QCheckBox, QSpinBox
)
from PySide6.QtCore import Qt

class CreateSequenceDialog(QDialog):
    def __init__(self, parent=None, schemas=None, current_user="postgres", db_type="postgres"):
        super().__init__(parent)
        self.setWindowTitle(f"Create Sequence ({db_type.capitalize()})")
        self.resize(600, 500)
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
            """)

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 18)
        main_layout.setSpacing(14)

        # Header
        title_lbl = QLabel("Create Sequence")
        title_lbl.setObjectName("dialogTitle")
        subtitle_lbl = QLabel(f"Define a new sequence in the <b>{db_type}</b> database.")
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
        self.name_input.setPlaceholderText("sequence_name")
        self.schema_combo = QComboBox()
        self.schema_combo.setEditable(True)
        
        if schemas:
            self.schema_combo.addItems(schemas)
        else:
            self.schema_combo.addItem("public" if db_type == 'postgres' else "main")
            
        gen_layout.addRow("Name:", self.name_input)
        if self.db_type == 'postgres':
            gen_layout.addRow("Schema:", self.schema_combo)
        
        self.tabs.addTab(self.general_tab, "General")

        # --- Tab 2: Sequence Options ---
        self.options_tab = QWidget()
        opt_layout = QFormLayout(self.options_tab)
        opt_layout.setContentsMargins(15, 15, 15, 15)
        opt_layout.setSpacing(12)
        
        # Start value
        self.start_value_input = QLineEdit()
        self.start_value_input.setPlaceholderText("1")
        self.start_value_input.setText("1")
        
        # Increment
        self.increment_input = QLineEdit()
        self.increment_input.setPlaceholderText("1")
        self.increment_input.setText("1")
        
        # Minimum value
        self.min_value_input = QLineEdit()
        self.min_value_input.setPlaceholderText("1 (or NO MINVALUE)")
        self.min_value_input.setText("1")
        
        # Maximum value
        self.max_value_input = QLineEdit()
        self.max_value_input.setPlaceholderText("922337203685477807 (or NO MAXVALUE)")
        self.max_value_input.setText("922337203685477807")
        
        # Cache
        self.cache_input = QLineEdit()
        self.cache_input.setPlaceholderText("1")
        self.cache_input.setText("1")
        
        # Cycle option
        self.cycle_check = QCheckBox("Cycle")
        self.cycle_check.setToolTip("Restart the sequence from the minimum value when max is reached")
        
        # Owned by table
        self.owned_by_input = QLineEdit()
        self.owned_by_input.setPlaceholderText("table_name.column_name (optional)")
        
        opt_layout.addRow("Start Value:", self.start_value_input)
        opt_layout.addRow("Increment:", self.increment_input)
        opt_layout.addRow("Minimum Value:", self.min_value_input)
        opt_layout.addRow("Maximum Value:", self.max_value_input)
        opt_layout.addRow("Cache:", self.cache_input)
        opt_layout.addRow("Cycle:", self.cycle_check)
        if self.db_type == 'postgres':
            opt_layout.addRow("Owned By:", self.owned_by_input)
        
        self.tabs.addTab(self.options_tab, "Options")

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
            QMessageBox.warning(self, "Error", "Sequence Name is required!")
            return
        
        # Validate numeric fields
        numeric_fields = [
            (self.start_value_input, "Start Value"),
            (self.increment_input, "Increment"),
            (self.cache_input, "Cache")
        ]
        
        for field, field_name in numeric_fields:
            value = field.text().strip()
            if value:
                try:
                    int(value)
                except ValueError:
                    QMessageBox.warning(self, "Error", f"{field_name} must be a valid integer!")
                    return
        
        # Optional validation for min/max
        if self.min_value_input.text().strip():
            try:
                int(self.min_value_input.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Error", "Minimum Value must be a valid integer or empty!")
                return
        
        if self.max_value_input.text().strip():
            try:
                int(self.max_value_input.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Error", "Maximum Value must be a valid integer or empty!")
                return
        
        self.accept()

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "schema": self.schema_combo.currentText(),
            "start_value": self.start_value_input.text().strip() or "1",
            "increment": self.increment_input.text().strip() or "1",
            "min_value": self.min_value_input.text().strip(),
            "max_value": self.max_value_input.text().strip(),
            "cache": self.cache_input.text().strip() or "1",
            "cycle": self.cycle_check.isChecked(),
            "owned_by": self.owned_by_input.text().strip()
        }
