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
    QCheckBox, QComboBox, QSpinBox, QFontComboBox, QScrollArea, QFrame,
    QListView, QStyledItemDelegate
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont
import qtawesome as qta
from ui.components import PrimaryButton, SecondaryButton


class FontPreviewDelegate(QStyledItemDelegate):
    """Renders each font name in its own typeface so the user can preview the font directly."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        font_name = index.data()
        if font_name:
            font = QFont(font_name)
            font.setPointSize(10)
            option.font = font

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(size.width(), max(size.height(), 26))


class PreferencesDialog(QDialog):
    """IDE-style preferences window with sidebar categories."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.setObjectName("preferencesDialog")
        self.main_window = main_window
        self.setWindowTitle("Preferences")
        self.resize(880, 660)
        self.setMinimumSize(780, 560)

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
        self._build_results_view_page()
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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #ffffff;
                border: none;
            }
        """)

        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
            }
        """)
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

    def _create_combo(self, min_contents_len: int = 16) -> QComboBox:
        """Helper to create dropdowns matching the UDS Virtual View dialog style."""
        combo = QComboBox(self)
        combo.setStyleSheet("combobox-popup: 0;")
        combo.setView(QListView())
        combo.setMaxVisibleItems(15)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(min_contents_len)
        return combo

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
        self.theme_combo = self._create_combo(16)
        self.theme_combo.addItems(["Grey (Default)", "Light Blue", "Light Green"])
        current_theme = getattr(self.main_window, "theme", "Grey (Default)")
        if current_theme in ("Light", "Dark"):
            current_theme = "Grey (Default)"
        self.theme_combo.setCurrentText(current_theme)
        form.addRow("Theme:", self.theme_combo)

        theme_help = QLabel("Application visual color theme.")
        theme_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        theme_help.setWordWrap(True)
        form.addRow("", theme_help)

        # 2. Default Connection
        self.default_conn_combo = self._create_combo(20)
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
        default_conn_help.setWordWrap(True)
        form.addRow("", default_conn_help)

        # 3. Confirm Tab Close
        self.confirm_tab_close_check = QCheckBox("Confirm before closing unsaved worksheet tabs")
        self.confirm_tab_close_check.setChecked(getattr(self.main_window, "confirm_tab_close", True))
        form.addRow("", self.confirm_tab_close_check)

        # 4. Restore Session on Startup
        self.restore_session_check = QCheckBox("Restore open tabs and window layout on startup")
        self.restore_session_check.setChecked(getattr(self.main_window, "restore_session_on_startup", True))
        form.addRow("", self.restore_session_check)

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
        self.editor_font_combo = QFontComboBox(self)
        self.editor_font_combo.setStyleSheet("combobox-popup: 0;")
        self.editor_font_combo.setView(QListView())
        self.editor_font_combo.setItemDelegate(FontPreviewDelegate(self.editor_font_combo))
        self.editor_font_combo.setMaxVisibleItems(15)
        self.editor_font_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.editor_font_combo.setMinimumContentsLength(16)
        self.editor_font_combo.setFontFilters(QFontComboBox.FontFilter.MonospacedFonts)
        saved_font = getattr(self.main_window, "editor_font_family", "Consolas")
        self.editor_font_combo.setCurrentFont(QFont(saved_font))
        form.addRow("Font Family:", self.editor_font_combo)

        font_family_help = QLabel("Monospaced font family used across SQL query editors.")
        font_family_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        font_family_help.setWordWrap(True)
        form.addRow("", font_family_help)

        # 2. Font Size
        self.editor_font_size_spin = QSpinBox()
        self.editor_font_size_spin.setRange(8, 32)
        self.editor_font_size_spin.setValue(getattr(self.main_window, "editor_font_size", 10))
        self.editor_font_size_spin.setSuffix(" pt")
        form.addRow("Font Size:", self.editor_font_size_spin)

        font_size_help = QLabel("Editor font size in points (Ctrl+Scroll in editor to zoom dynamically).")
        font_size_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        font_size_help.setWordWrap(True)
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

        # 6. Auto Completion / IntelliSense
        self.editor_autocomplete_check = QCheckBox("Enable SQL Auto-completion (IntelliSense popup)")
        self.editor_autocomplete_check.setChecked(getattr(self.main_window, "editor_autocomplete", True))
        form.addRow("", self.editor_autocomplete_check)

        # 7. Highlight Current Line
        self.editor_highlight_line_check = QCheckBox("Highlight current cursor line")
        self.editor_highlight_line_check.setChecked(getattr(self.main_window, "editor_highlight_line", True))
        form.addRow("", self.editor_highlight_line_check)

        # ── SQL Formatting & Code Style Sub-section ──
        form.addRow("", QLabel(""))  # spacer
        style_subheading = QLabel("SQL Formatting & Code Style")
        style_subheading.setStyleSheet("font-size: 11pt; font-weight: 700; color: #111827; margin-top: 4px;")
        form.addRow(style_subheading)

        # 8. Keyword Casing
        self.editor_keyword_casing_combo = self._create_combo(16)
        self.editor_keyword_casing_combo.addItems(["UPPERCASE", "lowercase", "Preserve (As-is)"])
        saved_kw_casing = getattr(self.main_window, "editor_keyword_casing", "UPPERCASE")
        idx = self.editor_keyword_casing_combo.findText(saved_kw_casing)
        if idx >= 0:
            self.editor_keyword_casing_combo.setCurrentIndex(idx)
        form.addRow("Keyword Casing:", self.editor_keyword_casing_combo)

        kw_help = QLabel("Casing applied to SQL keywords (SELECT, FROM, WHERE...) when typing or formatting.")
        kw_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        kw_help.setWordWrap(True)
        form.addRow("", kw_help)

        # 9. Identifier Casing
        self.editor_identifier_casing_combo = self._create_combo(16)
        self.editor_identifier_casing_combo.addItems(["lowercase", "UPPERCASE", "Preserve (As-is)"])
        saved_id_casing = getattr(self.main_window, "editor_identifier_casing", "Preserve (As-is)")
        idx = self.editor_identifier_casing_combo.findText(saved_id_casing)
        if idx >= 0:
            self.editor_identifier_casing_combo.setCurrentIndex(idx)
        form.addRow("Identifier Casing:", self.editor_identifier_casing_combo)

        id_help = QLabel("Casing style for schema names, tables, and column identifiers.")
        id_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        id_help.setWordWrap(True)
        form.addRow("", id_help)

        # 10. Auto-Close Characters
        self.editor_auto_close_chars_check = QCheckBox("Auto-close quotes and brackets ('', \"\", (), [], {})")
        self.editor_auto_close_chars_check.setChecked(getattr(self.main_window, "editor_auto_close_chars", True))
        form.addRow("", self.editor_auto_close_chars_check)

        # 11. Auto-Indent on Enter
        self.editor_auto_indent_check = QCheckBox("Auto-indent on Enter (maintain indent & step into blocks)")
        self.editor_auto_indent_check.setChecked(getattr(self.main_window, "editor_auto_indent", True))
        form.addRow("", self.editor_auto_indent_check)

        layout.addLayout(form)
        layout.addStretch()
        self.pages_stack.addWidget(scroll)

    def _build_results_view_page(self):
        item = QListWidgetItem(qta.icon("fa5s.table", color="#4b5563"), "Results & Grid")
        self.category_list.addItem(item)

        scroll, layout = self._create_page_scroll_area()
        layout.addWidget(self._create_section_header("Results & Data Grid", "Configure query output tables, cell presentation, and clipboard behaviors."))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setSpacing(12)

        # 1. NULL Value Representation
        self.grid_null_text_edit = QLineEdit()
        self.grid_null_text_edit.setPlaceholderText("NULL")
        saved_null = getattr(self.main_window, "grid_null_text", "NULL")
        self.grid_null_text_edit.setText(saved_null)
        form.addRow("NULL Value Display:", self.grid_null_text_edit)

        null_help = QLabel("Text displayed in cells representing SQL NULL values (e.g. NULL, (null), or empty).")
        null_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        null_help.setWordWrap(True)
        form.addRow("", null_help)

        # 2. DateTime Display Format
        self.grid_date_format_combo = self._create_combo(20)
        self.grid_date_format_combo.addItems([
            "YYYY-MM-DD HH:mm:ss",
            "ISO-8601 (YYYY-MM-DDTHH:mm:ss)",
            "MM/DD/YYYY HH:mm:ss",
            "DD/MM/YYYY HH:mm:ss",
            "Locale Default"
        ])
        saved_date_fmt = getattr(self.main_window, "grid_datetime_format", "YYYY-MM-DD HH:mm:ss")
        idx = self.grid_date_format_combo.findText(saved_date_fmt)
        if idx >= 0:
            self.grid_date_format_combo.setCurrentIndex(idx)
        form.addRow("Timestamp Format:", self.grid_date_format_combo)

        date_help = QLabel("Default formatting applied to date and timestamp values in results tables.")
        date_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        date_help.setWordWrap(True)
        form.addRow("", date_help)

        # 3. Default Page Size
        self.grid_page_size_combo = self._create_combo(16)
        self.grid_page_size_combo.addItems(["50", "100", "200", "500", "1000", "All (No Pagination)"])
        saved_page_size = getattr(self.main_window, "grid_page_size", "100")
        idx = self.grid_page_size_combo.findText(str(saved_page_size))
        if idx >= 0:
            self.grid_page_size_combo.setCurrentIndex(idx)
        form.addRow("Rows Per Page:", self.grid_page_size_combo)

        page_help = QLabel("Default number of rows displayed per page in query output views.")
        page_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        page_help.setWordWrap(True)
        form.addRow("", page_help)

        # 4. Show Vertical Header Row Numbers
        self.grid_show_row_numbers_check = QCheckBox("Show row numbers header (1, 2, 3...)")
        self.grid_show_row_numbers_check.setChecked(getattr(self.main_window, "grid_show_row_numbers", True))
        form.addRow("", self.grid_show_row_numbers_check)

        # 5. Copy Headers by Default
        self.grid_copy_headers_check = QCheckBox("Include column headers when copying selected cells")
        self.grid_copy_headers_check.setChecked(getattr(self.main_window, "grid_copy_headers", True))
        form.addRow("", self.grid_copy_headers_check)

        copy_help = QLabel("When enabled, copying cells (Ctrl+C) automatically prepends the header row.")
        copy_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        copy_help.setWordWrap(True)
        form.addRow("", copy_help)

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
        pg_help.setWordWrap(True)
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
        oracle_help.setWordWrap(True)
        form.addRow("", oracle_help)

        # Use WSL
        self.use_wsl_check = QCheckBox("Use WSL for PostgreSQL tools")
        self.use_wsl_check.setChecked(getattr(self.main_window, "use_wsl", False))
        form.addRow("", self.use_wsl_check)

        wsl_help = QLabel("Check this if your PostgreSQL tools are installed inside Linux (WSL).")
        wsl_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        wsl_help.setWordWrap(True)
        form.addRow("", wsl_help)

        # ── Query Execution & Results Sub-section ──
        form.addRow("", QLabel(""))  # spacer
        exec_subheading = QLabel("Query Execution & Results")
        exec_subheading.setStyleSheet("font-size: 11pt; font-weight: 700; color: #111827; margin-top: 4px;")
        form.addRow(exec_subheading)

        # Query Timeout
        self.query_timeout_spin = QSpinBox()
        self.query_timeout_spin.setRange(5, 3600)
        saved_timeout = getattr(self.main_window, "query_timeout_sec", 300)
        self.query_timeout_spin.setValue(int(saved_timeout))
        self.query_timeout_spin.setSuffix(" seconds")
        form.addRow("Query Timeout:", self.query_timeout_spin)

        timeout_help = QLabel("Maximum duration before an active worksheet query is automatically canceled (default: 300s).")
        timeout_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        timeout_help.setWordWrap(True)
        form.addRow("", timeout_help)

        # Default Query Row Limit
        self.default_row_limit_combo = self._create_combo(16)
        self.default_row_limit_combo.addItems(["No Limit", "100", "500", "1000", "5000"])
        saved_limit = getattr(self.main_window, "default_row_limit", "No Limit")
        idx = self.default_row_limit_combo.findText(str(saved_limit))
        if idx >= 0:
            self.default_row_limit_combo.setCurrentIndex(idx)
        form.addRow("Default Row Limit:", self.default_row_limit_combo)

        limit_help = QLabel("Default LIMIT applied to new query worksheets to prevent high memory usage on large tables.")
        limit_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        limit_help.setWordWrap(True)
        form.addRow("", limit_help)

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
        self.ai_provider_combo = self._create_combo(16)
        self.ai_provider_combo.addItems([
            "OpenAI",
            "Groq",
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
        provider_help.setWordWrap(True)
        form.addRow("", provider_help)

        # 2. Model Name
        self.ai_model_edit = QLineEdit()
        self.ai_model_edit.setText(getattr(self.main_window, "ai_model", ""))
        self.ai_model_edit.setPlaceholderText("e.g. gpt-4o-mini, qwen/qwen3.8-27b, gemini-1.5-flash")
        form.addRow("Model Name:", self.ai_model_edit)

        model_help = QLabel("Leave empty to use recommended default for the selected provider.")
        model_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        model_help.setWordWrap(True)
        form.addRow("", model_help)

        # 3. API Key
        self.ai_api_key_edit = QLineEdit()
        self.ai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_api_key_edit.setText(getattr(self.main_window, "ai_api_key", ""))
        self.ai_api_key_edit.setPlaceholderText("sk-... or gsk_... (leave blank for local Ollama)")
        form.addRow("API Key:", self.ai_api_key_edit)

        key_help = QLabel("Securely stored locally. Not required when running a local Ollama instance.")
        key_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        key_help.setWordWrap(True)
        form.addRow("", key_help)

        # 4. Custom Base URL
        self.ai_base_url_edit = QLineEdit()
        self.ai_base_url_edit.setText(getattr(self.main_window, "ai_base_url", ""))
        self.ai_base_url_edit.setPlaceholderText("e.g. https://api.groq.com/openai/v1 or http://localhost:11434/v1")
        form.addRow("Base URL (Optional):", self.ai_base_url_edit)

        url_help = QLabel("Custom endpoint. Leave blank to automatically use official provider endpoints.")
        url_help.setStyleSheet("color: #6b7280; font-size: 8pt;")
        url_help.setWordWrap(True)
        form.addRow("", url_help)

        # Provider change handler to adjust placeholders
        def on_provider_changed(text):
            if "Groq" in text:
                if not self.ai_base_url_edit.text():
                    self.ai_base_url_edit.setPlaceholderText("https://api.groq.com/openai/v1")
                if not self.ai_model_edit.text():
                    self.ai_model_edit.setPlaceholderText("qwen/qwen3.8-27b")
            elif "Ollama" in text:
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
        self.confirm_tab_close_check.setChecked(True)
        self.restore_session_check.setChecked(True)

        self.editor_font_combo.setCurrentFont(QFont("Consolas"))
        self.editor_font_size_spin.setValue(10)
        self.editor_tab_size_spin.setValue(4)
        self.editor_word_wrap_check.setChecked(False)
        self.editor_line_numbers_check.setChecked(True)
        self.editor_autocomplete_check.setChecked(True)
        self.editor_highlight_line_check.setChecked(True)
        self.editor_keyword_casing_combo.setCurrentText("UPPERCASE")
        self.editor_identifier_casing_combo.setCurrentText("Preserve (As-is)")
        self.editor_auto_close_chars_check.setChecked(True)
        self.editor_auto_indent_check.setChecked(True)

        self.grid_null_text_edit.setText("NULL")
        self.grid_date_format_combo.setCurrentText("YYYY-MM-DD HH:mm:ss")
        self.grid_page_size_combo.setCurrentText("100")
        self.grid_show_row_numbers_check.setChecked(True)
        self.grid_copy_headers_check.setChecked(True)

        self.pg_bin_edit.setText("")
        self.oracle_bin_edit.setText("")
        self.use_wsl_check.setChecked(False)
        self.query_timeout_spin.setValue(300)
        self.default_row_limit_combo.setCurrentText("No Limit")

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
            "confirm_tab_close": self.confirm_tab_close_check.isChecked(),
            "restore_session_on_startup": self.restore_session_check.isChecked(),

            # Editor
            "editor_font_family": self.editor_font_combo.currentFont().family(),
            "editor_font_size": self.editor_font_size_spin.value(),
            "editor_tab_size": self.editor_tab_size_spin.value(),
            "editor_word_wrap": self.editor_word_wrap_check.isChecked(),
            "editor_line_numbers": self.editor_line_numbers_check.isChecked(),
            "editor_autocomplete": self.editor_autocomplete_check.isChecked(),
            "editor_highlight_line": self.editor_highlight_line_check.isChecked(),
            "editor_keyword_casing": self.editor_keyword_casing_combo.currentText(),
            "editor_identifier_casing": self.editor_identifier_casing_combo.currentText(),
            "editor_auto_close_chars": self.editor_auto_close_chars_check.isChecked(),
            "editor_auto_indent": self.editor_auto_indent_check.isChecked(),

            # Results & Grid
            "grid_null_text": self.grid_null_text_edit.text(),
            "grid_datetime_format": self.grid_date_format_combo.currentText(),
            "grid_page_size": self.grid_page_size_combo.currentText(),
            "grid_show_row_numbers": self.grid_show_row_numbers_check.isChecked(),
            "grid_copy_headers": self.grid_copy_headers_check.isChecked(),

            # Database Tools & Execution
            "pg_bin_path": self.pg_bin_edit.text().strip(),
            "oracle_bin_path": self.oracle_bin_edit.text().strip(),
            "use_wsl": self.use_wsl_check.isChecked(),
            "query_timeout_sec": self.query_timeout_spin.value(),
            "default_row_limit": self.default_row_limit_combo.currentText(),

            # AI Assistant
            "ai_provider": self.ai_provider_combo.currentText(),
            "ai_model": self.ai_model_edit.text().strip(),
            "ai_api_key": self.ai_api_key_edit.text().strip(),
            "ai_base_url": self.ai_base_url_edit.text().strip(),
        }

