# dialogs/preferences/dialog.py
"""
Multi-category IDE-style Preferences Dialog for DB Explorer.
Provides categorized settings:
- General / Appearance (Theme, Default Connection)
- Text Editor (Font Family, Font Size, Tab Size, Word Wrap, Line Numbers)
- Database Tools & Binaries (PostgreSQL bin path, Oracle bin path, WSL mode)
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, QListWidgetItem,
    QStackedWidget, QWidget, QFormLayout, QLineEdit, QFileDialog, QLabel,
    QCheckBox, QComboBox, QSpinBox, QFontComboBox, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont
import qtawesome as qta
from ui.components import PrimaryButton, SecondaryButton


class PreferencesDialog(QDialog):
    """IDE-style preferences window with sidebar categories."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Preferences")
        self.resize(760, 560)
        self.setMinimumSize(640, 460)

        self.setup_ui()

    def setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # Main splitter (Categories on left, Pages on right)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #d1d5db;
            }
        """)

        # ── Left: Category List ─────────────────────────────────────────
        self.category_list = QListWidget()
        self.category_list.setFixedWidth(200)
        self.category_list.setIconSize(QSize(18, 18))
        self.category_list.setStyleSheet("""
            QListWidget {
                background-color: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                outline: none;
                padding: 6px;
                font-size: 9.5pt;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-radius: 4px;
                color: #374151;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background-color: #f3f4f6;
                color: #111827;
            }
            QListWidget::item:selected {
                background-color: #e5e7eb;
                color: #111827;
                font-weight: 600;
            }
        """)

        # ── Right: Stacked Pages ─────────────────────────────────────────
        self.pages_stack = QStackedWidget()
        self.pages_stack.setStyleSheet("""
            QStackedWidget {
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
            }
        """)

        # Build Pages
        self._build_general_page()
        self._build_editor_page()
        self._build_database_tools_page()
        self._build_ai_assistant_page()

        # Connect category list selection
        self.category_list.currentRowChanged.connect(self.pages_stack.setCurrentIndex)
        self.category_list.setCurrentRow(0)

        splitter.addWidget(self.category_list)
        splitter.addWidget(self.pages_stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root_layout.addWidget(splitter, stretch=1)

        # ── Bottom Action Buttons ───────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 4, 0, 0)
        btn_layout.setSpacing(8)

        reset_btn = SecondaryButton("Restore Defaults")
        reset_btn.setToolTip("Reset all settings to recommended defaults")
        reset_btn.clicked.connect(self.restore_defaults)

        btn_layout.addWidget(reset_btn)
        btn_layout.addStretch()

        cancel_btn = SecondaryButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = PrimaryButton("OK")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        root_layout.addLayout(btn_layout)

    # ── Page Builders ───────────────────────────────────────────────────

    def _create_page_scroll_area(self):
        """Creates a styled scroll area container for a settings page."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }")
        
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        scroll.setWidget(container)
        return scroll, layout

    def _create_section_header(self, title: str, subtitle: str = ""):
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(2)

        lbl = QLabel(title)
        lbl.setStyleSheet("font-size: 13pt; font-weight: 700; color: #111827;")
        layout.addWidget(lbl)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setStyleSheet("font-size: 8.5pt; color: #6b7280;")
            sub.setWordWrap(True)
            layout.addWidget(sub)

        return header

    def _build_general_page(self):
        item = QListWidgetItem(qta.icon("fa5s.sliders-h", color="#4b5563"), "General")
        self.category_list.addItem(item)

        scroll, layout = self._create_page_scroll_area()
        layout.addWidget(self._create_section_header("General Settings", "Configure application appearance and default behaviors."))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setSpacing(12)

        # 1. Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Grey (Default)", "Light Blue", "Light Green"])
        current_theme = getattr(self.main_window, "theme", "Grey (Default)")
        if current_theme in ("Light", "Dark"):
            current_theme = "Grey (Default)"
        self.theme_combo.setCurrentText(current_theme)
        form.addRow("Theme:", self.theme_combo)

        theme_help = QLabel("Application visual color theme.")
        theme_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        form.addRow("", theme_help)

        # 2. Default Connection
        self.default_conn_combo = QComboBox()
        self.default_conn_combo.addItem("None (First Available)", None)
        try:
            import db
            connections = db.get_all_connections_from_db()
            for conn in connections:
                self.default_conn_combo.addItem(conn["display_name"], conn["id"])
        except Exception as e:
            print(f"Error loading connections for preferences: {e}")

        saved_default_id = getattr(self.main_window, "default_connection_id", None)
        if saved_default_id is not None:
            idx = self.default_conn_combo.findData(saved_default_id)
            if idx >= 0:
                self.default_conn_combo.setCurrentIndex(idx)

        form.addRow("Default Connection:", self.default_conn_combo)

        default_conn_help = QLabel("Default active connection pre-selected when opening a new worksheet.")
        default_conn_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        form.addRow("", default_conn_help)

        layout.addLayout(form)
        layout.addStretch()
        self.pages_stack.addWidget(scroll)

    def _build_editor_page(self):
        item = QListWidgetItem(qta.icon("fa5s.code", color="#4b5563"), "Text Editor")
        self.category_list.addItem(item)

        scroll, layout = self._create_page_scroll_area()
        layout.addWidget(self._create_section_header("Text Editor", "Configure font, spacing, and editing behavior for SQL worksheets."))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setSpacing(12)

        # 1. Font Family
        self.editor_font_combo = QFontComboBox()
        self.editor_font_combo.setFontFilters(QFontComboBox.FontFilter.MonospacedFonts)
        saved_font = getattr(self.main_window, "editor_font_family", "Consolas")
        self.editor_font_combo.setCurrentFont(QFont(saved_font))
        form.addRow("Font Family:", self.editor_font_combo)

        font_family_help = QLabel("Monospaced font family used across SQL query editors.")
        font_family_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        form.addRow("", font_family_help)

        # 2. Font Size
        self.editor_font_size_spin = QSpinBox()
        self.editor_font_size_spin.setRange(8, 32)
        self.editor_font_size_spin.setValue(getattr(self.main_window, "editor_font_size", 10))
        self.editor_font_size_spin.setSuffix(" pt")
        form.addRow("Font Size:", self.editor_font_size_spin)

        font_size_help = QLabel("Editor font size in points (Ctrl+Scroll in editor to zoom dynamically).")
        font_size_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        form.addRow("", font_size_help)

        # 3. Tab Size
        self.editor_tab_size_spin = QSpinBox()
        self.editor_tab_size_spin.setRange(2, 8)
        self.editor_tab_size_spin.setValue(getattr(self.main_window, "editor_tab_size", 4))
        self.editor_tab_size_spin.setSuffix(" spaces")
        form.addRow("Tab Size:", self.editor_tab_size_spin)

        # 4. Word Wrap
        self.editor_word_wrap_check = QCheckBox("Enable Word Wrap")
        self.editor_word_wrap_check.setChecked(getattr(self.main_window, "editor_word_wrap", False))
        form.addRow("", self.editor_word_wrap_check)

        # 5. Line Numbers
        self.editor_line_numbers_check = QCheckBox("Show Line Numbers")
        self.editor_line_numbers_check.setChecked(getattr(self.main_window, "editor_line_numbers", True))
        form.addRow("", self.editor_line_numbers_check)

        # 6. Auto Uppercase Keywords
        self.editor_auto_uppercase_check = QCheckBox("Automatically uppercase SQL keywords")
        self.editor_auto_uppercase_check.setChecked(getattr(self.main_window, "editor_auto_uppercase", True))
        form.addRow("", self.editor_auto_uppercase_check)

        layout.addLayout(form)
        layout.addStretch()
        self.pages_stack.addWidget(scroll)

    def _build_database_tools_page(self):
        item = QListWidgetItem(qta.icon("fa5s.database", color="#4b5563"), "Database Tools")
        self.category_list.addItem(item)

        scroll, layout = self._create_page_scroll_area()
        layout.addWidget(self._create_section_header("Database Tools & Binaries", "Configure CLI executables, dump/restore utilities, and platform options."))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setSpacing(12)

        # Postgres Bin Path
        self.pg_bin_edit = QLineEdit()
        self.pg_bin_edit.setText(getattr(self.main_window, "pg_bin_path", ""))
        self.pg_bin_edit.setPlaceholderText("e.g. C:\\Program Files\\PostgreSQL\\15\\bin")

        pg_bin_btn = SecondaryButton("Browse...")
        pg_bin_btn.clicked.connect(self.browse_pg_bin)

        pg_bin_layout = QHBoxLayout()
        pg_bin_layout.setContentsMargins(0, 0, 0, 0)
        pg_bin_layout.addWidget(self.pg_bin_edit)
        pg_bin_layout.addWidget(pg_bin_btn)

        form.addRow("PostgreSQL Binary Path:", pg_bin_layout)

        pg_help = QLabel("Directory containing pg_dump, pg_restore, and psql.")
        pg_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        form.addRow("", pg_help)

        # Oracle Bin Path
        self.oracle_bin_edit = QLineEdit()
        self.oracle_bin_edit.setText(getattr(self.main_window, "oracle_bin_path", ""))
        self.oracle_bin_edit.setPlaceholderText("e.g. C:\\oracle\\product\\19.0.0\\client_1\\bin")

        oracle_bin_btn = SecondaryButton("Browse...")
        oracle_bin_btn.clicked.connect(self.browse_oracle_bin)

        oracle_bin_layout = QHBoxLayout()
        oracle_bin_layout.setContentsMargins(0, 0, 0, 0)
        oracle_bin_layout.addWidget(self.oracle_bin_edit)
        oracle_bin_layout.addWidget(oracle_bin_btn)

        form.addRow("Oracle Binary Path:", oracle_bin_layout)

        oracle_help = QLabel("Directory containing sqlplus and Oracle client utilities.")
        oracle_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        form.addRow("", oracle_help)

        # Use WSL
        self.use_wsl_check = QCheckBox("Use WSL for PostgreSQL tools")
        self.use_wsl_check.setChecked(getattr(self.main_window, "use_wsl", False))
        form.addRow("", self.use_wsl_check)

        wsl_help = QLabel("Check this if your PostgreSQL tools are installed inside Linux (WSL).")
        wsl_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        form.addRow("", wsl_help)

        layout.addLayout(form)
        layout.addStretch()
        self.pages_stack.addWidget(scroll)

    def _build_ai_assistant_page(self):
        item = QListWidgetItem(qta.icon("fa5s.robot", color="#4b5563"), "AI Assistant")
        self.category_list.addItem(item)

        scroll, layout = self._create_page_scroll_area()
        layout.addWidget(self._create_section_header("AI Assistant", "Configure AI models for query explanations, performance tuning, and SQL chat."))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setSpacing(12)

        # 1. AI Provider
        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.addItems([
            "OpenAI",
            "Google Gemini",
            "Anthropic Claude",
            "Ollama (Local)",
            "Custom (OpenAI-compatible)"
        ])
        saved_provider = getattr(self.main_window, "ai_provider", "OpenAI")
        idx = self.ai_provider_combo.findText(saved_provider)
        if idx >= 0:
            self.ai_provider_combo.setCurrentIndex(idx)
        form.addRow("AI Provider:", self.ai_provider_combo)

        provider_help = QLabel("Select your preferred AI provider or local offline runner.")
        provider_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        form.addRow("", provider_help)

        # 2. Model Name
        self.ai_model_edit = QLineEdit()
        self.ai_model_edit.setText(getattr(self.main_window, "ai_model", ""))
        self.ai_model_edit.setPlaceholderText("e.g. gpt-4o-mini, gemini-1.5-flash, llama3")
        form.addRow("Model Name:", self.ai_model_edit)

        model_help = QLabel("Leave empty to use recommended default for the selected provider.")
        model_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        form.addRow("", model_help)

        # 3. API Key
        self.ai_api_key_edit = QLineEdit()
        self.ai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_api_key_edit.setText(getattr(self.main_window, "ai_api_key", ""))
        self.ai_api_key_edit.setPlaceholderText("sk-... or API key (leave blank for local Ollama / offline)")
        form.addRow("API Key:", self.ai_api_key_edit)

        key_help = QLabel("Securely stored locally. If left blank, intelligent offline SQL analysis is used.")
        key_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        form.addRow("", key_help)

        # 4. Custom Base URL
        self.ai_base_url_edit = QLineEdit()
        self.ai_base_url_edit.setText(getattr(self.main_window, "ai_base_url", ""))
        self.ai_base_url_edit.setPlaceholderText("e.g. http://localhost:11434/v1 or custom proxy")
        form.addRow("Base URL (Optional):", self.ai_base_url_edit)

        url_help = QLabel("Custom endpoint. Defaults to provider official URL or http://localhost:11434/v1 for Ollama.")
        url_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        form.addRow("", url_help)

        # Provider change handler to adjust placeholders
        def on_provider_changed(text):
            if "Ollama" in text:
                if not self.ai_base_url_edit.text():
                    self.ai_base_url_edit.setPlaceholderText("http://localhost:11434/v1")
                if not self.ai_model_edit.text():
                    self.ai_model_edit.setPlaceholderText("llama3")
            elif "Gemini" in text:
                if not self.ai_model_edit.text():
                    self.ai_model_edit.setPlaceholderText("gemini-1.5-flash")
            elif "Claude" in text:
                if not self.ai_model_edit.text():
                    self.ai_model_edit.setPlaceholderText("claude-3-5-sonnet-20241022")
            else:
                if not self.ai_model_edit.text():
                    self.ai_model_edit.setPlaceholderText("gpt-4o-mini")

        self.ai_provider_combo.currentTextChanged.connect(on_provider_changed)

        layout.addLayout(form)
        layout.addStretch()
        self.pages_stack.addWidget(scroll)

    # ── Browse Handlers ─────────────────────────────────────────────────

    def browse_pg_bin(self):
        directory = QFileDialog.getExistingDirectory(self, "Select PostgreSQL Bin Directory", self.pg_bin_edit.text())
        if directory:
            self.pg_bin_edit.setText(directory)

    def browse_oracle_bin(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Oracle Bin Directory", self.oracle_bin_edit.text())
        if directory:
            self.oracle_bin_edit.setText(directory)

    # ── Defaults & Values ───────────────────────────────────────────────

    def restore_defaults(self):
        """Restores setting values in UI to default states."""
        self.theme_combo.setCurrentText("Grey (Default)")
        self.default_conn_combo.setCurrentIndex(0)
        self.editor_font_combo.setCurrentFont(QFont("Consolas"))
        self.editor_font_size_spin.setValue(10)
        self.editor_tab_size_spin.setValue(4)
        self.editor_word_wrap_check.setChecked(False)
        self.editor_line_numbers_check.setChecked(True)
        self.editor_auto_uppercase_check.setChecked(True)
        self.use_wsl_check.setChecked(False)
        self.ai_provider_combo.setCurrentText("OpenAI")
        self.ai_model_edit.setText("")
        self.ai_api_key_edit.setText("")
        self.ai_base_url_edit.setText("")

    def get_settings(self):
        """Returns collected dictionary of preference settings."""
        return {
            # General
            "theme": self.theme_combo.currentText(),
            "default_connection_id": self.default_conn_combo.currentData(),

            # Editor
            "editor_font_family": self.editor_font_combo.currentFont().family(),
            "editor_font_size": self.editor_font_size_spin.value(),
            "editor_tab_size": self.editor_tab_size_spin.value(),
            "editor_word_wrap": self.editor_word_wrap_check.isChecked(),
            "editor_line_numbers": self.editor_line_numbers_check.isChecked(),
            "editor_auto_uppercase": self.editor_auto_uppercase_check.isChecked(),

            # Database Tools
            "pg_bin_path": self.pg_bin_edit.text().strip(),
            "oracle_bin_path": self.oracle_bin_edit.text().strip(),
            "use_wsl": self.use_wsl_check.isChecked(),

            # AI Assistant
            "ai_provider": self.ai_provider_combo.currentText(),
            "ai_model": self.ai_model_edit.text().strip(),
            "ai_api_key": self.ai_api_key_edit.text().strip(),
            "ai_base_url": self.ai_base_url_edit.text().strip(),
        }

