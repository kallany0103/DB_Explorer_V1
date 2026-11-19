# dialogs/preferences/dialog.py
"""Modern searchable Settings dialog with card-based rows and live Apply support."""

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFontComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

from ui.components import (
    PasswordBox,
    PrimaryButton,
    SearchBox,
    SecondaryButton,
    SettingsCategoryDelegate,
    ToggleSwitch,
)
from pathlib import Path
from typing import Any

from ui.dialog_utils import fit_dialog_to_screen
from ui.feature_flags import (
    FEATURE_CATALOG,
    FEATURE_SPEC_BY_KEY,
    is_connection_type_enabled,
    normalize_feature_flags,
)
from widgets.psql_tool.discovery import get_all_postgres_candidates
from widgets.sqlplus_tool.discovery import get_sqlplus_candidates


class BinaryPathSelector(QWidget):
    """Dropdown selector for CLI client binaries with auto-detection and custom browse."""

    path_changed = Signal(str)

    def __init__(
        self,
        current_val: str,
        candidates: list[dict[str, Any]],
        dialog_title: str,
        parent=None,
        use_wsl: bool = False,
        wsl_distro: str | None = None,
    ):
        super().__init__(parent)
        self._current_val = (current_val or "").strip()
        self._candidates = candidates
        self._dialog_title = dialog_title
        self._use_wsl = use_wsl
        self._wsl_distro = wsl_distro
        self._prev_index = 0
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(3)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        self.combo = QComboBox()
        self.combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.combo.setMinimumWidth(240)

        if self._candidates:
            for i, c in enumerate(self._candidates):
                user_data = f"wsl:{c['distro']}" if c.get("kind") == "wsl" else ("" if i == 0 else c.get("dir", ""))
                self.combo.addItem(c["name"], userData=user_data)
        else:
            self.combo.addItem("Not detected", userData="")

        # Option to explicitly unselect / disable the binary path
        self.combo.addItem("None (Disabled)", userData="none")

        custom_idx = -1
        matched_cand_idx = -1

        if self._use_wsl:
            for i, c in enumerate(self._candidates):
                if c.get("kind") == "wsl":
                    if self._wsl_distro and c.get("distro") == self._wsl_distro:
                        matched_cand_idx = i
                        break
                    elif matched_cand_idx < 0:
                        matched_cand_idx = i
        elif self._current_val:
            if self._current_val.lower() == "none":
                none_idx = self.combo.findData("none")
                if none_idx >= 0:
                    matched_cand_idx = none_idx
            else:
                val_p = Path(self._current_val)
                val_norm = str(val_p.resolve() if val_p.exists() else val_p).lower()
                val_parent_norm = str(val_p.parent.resolve() if val_p.parent.exists() else val_p.parent).lower()

                for i, c in enumerate(self._candidates):
                    if c.get("kind") == "wsl":
                        continue
                    c_dir = str(Path(c["dir"]).resolve() if Path(c["dir"]).exists() else c["dir"]).lower()
                    c_path = str(Path(c["path"]).resolve() if Path(c["path"]).exists() else c["path"]).lower()
                    if val_norm in (c_dir, c_path) or (val_p.name.lower() in ("bin", "runtime") and val_parent_norm in (c_dir, c_path)):
                        matched_cand_idx = i
                        break

                if matched_cand_idx < 0:
                    folder_name = val_p.parent.name if val_p.name.lower() in ("bin", "runtime") else (val_p.name or self._current_val)
                    self.combo.addItem(f"Custom: {folder_name}", userData=self._current_val)
                    custom_idx = self.combo.count() - 1

        self.combo.addItem("Browse custom path...", userData="__browse__")

        if custom_idx >= 0:
            self.combo.setCurrentIndex(custom_idx)
            self._prev_index = custom_idx
        elif matched_cand_idx >= 0:
            self.combo.setCurrentIndex(matched_cand_idx)
            self._prev_index = matched_cand_idx
        else:
            self.combo.setCurrentIndex(0)
            self._prev_index = 0

        row_layout.addWidget(self.combo, 1)

        self.browse_btn = SecondaryButton("Browse...")
        self.browse_btn.setAutoDefault(False)
        self.browse_btn.clicked.connect(self._on_browse_clicked)
        row_layout.addWidget(self.browse_btn)

        root.addWidget(row)

        self.status_lbl = QLabel()
        self.status_lbl.setObjectName("settingsBinaryStatusLbl")
        self.status_lbl.setStyleSheet("font-size: 8pt; padding-left: 2px;")
        root.addWidget(self.status_lbl)

        self.combo.currentIndexChanged.connect(self._on_combo_changed)
        self._update_status()

    def get_selected_candidate(self) -> dict[str, Any] | None:
        idx = self.combo.currentIndex()
        if 0 <= idx < len(self._candidates):
            return self._candidates[idx]
        return None

    def get_selected_info(self) -> dict[str, Any]:
        cand = self.get_selected_candidate()
        if cand and cand.get("kind") == "wsl":
            return {
                "use_wsl": True,
                "wsl_distro": cand.get("distro"),
                "pg_bin_path": "",
            }
        val = self.get_value()
        return {
            "use_wsl": False,
            "wsl_distro": None,
            "pg_bin_path": val,
        }

    def set_selected_info(self, pg_bin_path: str = "", use_wsl: bool = False, wsl_distro: str | None = None) -> None:
        if use_wsl:
            for i, c in enumerate(self._candidates):
                if c.get("kind") == "wsl":
                    if wsl_distro and c.get("distro") == wsl_distro:
                        self.combo.setCurrentIndex(i)
                        self._prev_index = i
                        self._update_status()
                        return
                    elif not wsl_distro:
                        self.combo.setCurrentIndex(i)
                        self._prev_index = i
                        self._update_status()
                        return
        self.set_value(pg_bin_path)

    def _on_combo_changed(self, index: int):
        data = self.combo.itemData(index)
        if data == "__browse__":
            self._on_browse_clicked()
        else:
            self._prev_index = index
            self._update_status()
            self.path_changed.emit(self.get_value())

    def _on_browse_clicked(self):
        cur = self.get_value()
        start_dir = cur if cur and not cur.startswith("wsl:") and cur != "none" else ""
        directory = QFileDialog.getExistingDirectory(self, self._dialog_title, start_dir)
        if directory:
            self.set_custom_path(directory)
            self.path_changed.emit(directory)
        else:
            if self.combo.currentData() == "__browse__":
                self.combo.setCurrentIndex(self._prev_index)

    def set_custom_path(self, path: str):
        val_p = Path(path)
        val_norm = str(val_p.resolve() if val_p.exists() else val_p).lower()
        val_parent_norm = str(val_p.parent.resolve() if val_p.parent.exists() else val_p.parent).lower()

        for i, c in enumerate(self._candidates):
            if c.get("kind") == "wsl":
                continue
            c_dir = str(Path(c["dir"]).resolve() if Path(c["dir"]).exists() else c["dir"]).lower()
            c_path = str(Path(c["path"]).resolve() if Path(c["path"]).exists() else c["path"]).lower()
            if val_norm in (c_dir, c_path) or (val_p.name.lower() in ("bin", "runtime") and val_parent_norm in (c_dir, c_path)):
                self.combo.setCurrentIndex(i)
                self._prev_index = i
                self._update_status()
                return

        for i in range(self.combo.count()):
            item_val = str(self.combo.itemData(i) or "").lower()
            if item_val in (val_norm, path.lower(), val_parent_norm):
                self.combo.setCurrentIndex(i)
                self._prev_index = i
                self._update_status()
                return

        insert_idx = max(0, self.combo.count() - 1)
        folder_name = val_p.parent.name if val_p.name.lower() in ("bin", "runtime") else (val_p.name or path)
        self.combo.insertItem(insert_idx, f"Custom: {folder_name}", userData=path)
        self.combo.setCurrentIndex(insert_idx)
        self._prev_index = insert_idx
        self._update_status()

    def get_value(self) -> str:
        cand = self.get_selected_candidate()
        if cand and cand.get("kind") == "wsl":
            return f"wsl:{cand.get('distro', '')}"
        data = self.combo.currentData()
        return "" if not data or data == "__browse__" else str(data)

    def set_value(self, val: str):
        if not val:
            self.combo.setCurrentIndex(0)
            self._prev_index = 0
        elif str(val).lower() == "none":
            none_idx = self.combo.findData("none")
            if none_idx >= 0:
                self.combo.setCurrentIndex(none_idx)
                self._prev_index = none_idx
        elif str(val).startswith("wsl:"):
            target_distro = str(val).split(":", 1)[1]
            for i, c in enumerate(self._candidates):
                if c.get("kind") == "wsl" and c.get("distro") == target_distro:
                    self.combo.setCurrentIndex(i)
                    self._prev_index = i
                    break
        else:
            self.set_custom_path(val)
        self._update_status()

    def _update_status(self):
        cand = self.get_selected_candidate()
        if cand and cand.get("kind") == "wsl":
            distro = cand.get("distro", "WSL")
            if cand.get("available", True):
                path_str = cand.get("path") or "/usr/bin/psql"
                self.status_lbl.setText(f"Active: WSL {distro} ({path_str})")
                self.status_lbl.setToolTip(f"WSL distribution: {distro}\nDetected binary: {path_str}\n{cand.get('version', '')}")
                self.status_lbl.setStyleSheet("color: #059669; font-size: 8pt;")
            else:
                self.status_lbl.setText(f"Not found: psql not installed in WSL {distro}")
                self.status_lbl.setToolTip(f"PostgreSQL client binaries were not found inside {distro}.")
                self.status_lbl.setStyleSheet("color: #dc2626; font-size: 8pt;")
            return

        val = self.get_value()
        if str(val).lower() == "none":
            self.status_lbl.setText("Disabled (No client selected)")
            self.status_lbl.setToolTip("CLI binary execution is unselected / disabled.")
            self.status_lbl.setStyleSheet("color: #64748b; font-size: 8pt;")
            return

        if not val and self._candidates:
            active_p = self._candidates[0]["path"]
            short_p = active_p if len(active_p) <= 50 else ("..." + active_p[-47:])
            self.status_lbl.setText(f"Active: {short_p}")
            self.status_lbl.setToolTip(f"Auto-detected client:\n{active_p}")
            self.status_lbl.setStyleSheet("color: #059669; font-size: 8pt;")
        elif val and not val.startswith("wsl:"):
            val_p = Path(val)
            val_norm = str(val_p.resolve() if val_p.exists() else val_p).lower()
            val_parent_norm = str(val_p.parent.resolve() if val_p.parent.exists() else val_p.parent).lower()

            matched_cand = None
            for c in self._candidates:
                if c.get("kind") == "wsl":
                    continue
                c_dir = str(Path(c["dir"]).resolve() if Path(c["dir"]).exists() else c["dir"]).lower()
                c_path = str(Path(c["path"]).resolve() if Path(c["path"]).exists() else c["path"]).lower()
                if val_norm in (c_dir, c_path) or (val_p.name.lower() in ("bin", "runtime") and val_parent_norm in (c_dir, c_path)):
                    matched_cand = c
                    break

            display_p = matched_cand["path"] if matched_cand else val
            short_val = display_p if len(display_p) <= 50 else ("..." + display_p[-47:])
            self.status_lbl.setText(f"Using: {short_val}")
            self.status_lbl.setToolTip(f"Configured client:\n{display_p}")
            self.status_lbl.setStyleSheet("color: #2563eb; font-size: 8pt;")
        else:
            self.status_lbl.setText("Not found on system")
            self.status_lbl.setToolTip("No executable detected. Please install client or browse for folder.")
            self.status_lbl.setStyleSheet("color: #dc2626; font-size: 8pt;")


class FontPreviewDelegate(QStyledItemDelegate):
    """Render each font item in its own typeface inside the font selector."""

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
    """Master-detail Settings window with live search, card rows, and Apply support."""

    settings_applied = Signal(dict)

    def __init__(self, main_window):
        super().__init__(main_window)
        self.setObjectName("preferencesDialog")
        self.main_window = main_window
        self.setWindowTitle("Settings")
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        fit_dialog_to_screen(self, ideal_width=740, ideal_height=500, min_width=580, min_height=380)

        self._search_entries: list[dict] = []
        self._page_cards: dict[int, list[dict]] = {}
        self._page_setting_keys: dict[int, tuple[str, ...]] = {}
        self.feature_checks: dict[str, ToggleSwitch] = {}
        self._baseline_settings: dict = {}
        self._default_settings: dict = {}
        self._is_initializing = True

        self.setup_ui()
        self._baseline_settings = self.get_settings()
        self._default_settings = self._build_default_settings()
        self._is_initializing = False
        self._sync_footer_state()

    def setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        body_layout.addWidget(self._build_sidebar())
        body_layout.addWidget(self._build_content_area(), stretch=1)
        root_layout.addWidget(body, stretch=1)
        root_layout.addWidget(self._build_footer())

        self._build_general_page()
        self._build_features_page()
        self._build_editor_page()
        self._build_results_view_page()
        self._build_database_tools_page()
        self._build_ai_assistant_page()

        self.category_list.currentRowChanged.connect(self._on_category_changed)
        self.category_list.setCurrentRow(0)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("settingsSidebar")
        sidebar.setFixedWidth(190)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(10)

        title = QLabel("Settings")
        title.setObjectName("settingsSidebarTitle")
        layout.addWidget(title)

        self.search_edit = SearchBox("Search settings...")
        self.search_edit.setObjectName("settingsSearchEdit")
        self.search_edit.setStyleSheet("")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_settings)
        layout.addWidget(self.search_edit)

        self.category_list = QListWidget()
        self.category_list.setObjectName("settingsCategoryList")
        self.category_list.setMouseTracking(True)
        self.category_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.category_list.setItemDelegate(SettingsCategoryDelegate(self.category_list))
        self.category_list.setIconSize(QSize(16, 16))
        layout.addWidget(self.category_list, stretch=1)
        return sidebar

    def _build_content_area(self) -> QWidget:
        area = QWidget()
        area.setObjectName("settingsContentArea")
        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.pages_stack = QStackedWidget()
        self.pages_stack.setObjectName("settingsPagesStack")
        layout.addWidget(self.pages_stack, stretch=1)

        self.search_empty_label = QLabel("No matching settings found.")
        self.search_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.search_empty_label.setObjectName("settingsRowDesc")
        self.search_empty_label.hide()
        layout.addWidget(self.search_empty_label)
        return area

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("settingsFooterBar")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(8)

        self.reset_btn = SecondaryButton("Restore Defaults")
        self.reset_btn.setAutoDefault(False)
        self.reset_btn.setToolTip("Reset all settings to recommended defaults")
        self.reset_btn.clicked.connect(self.restore_defaults)
        layout.addWidget(self.reset_btn)
        layout.addStretch()

        self.apply_feedback_label = QLabel("Applied")
        self.apply_feedback_label.setObjectName("settingsApplyFeedbackLabel")
        self.apply_feedback_label.hide()
        layout.addWidget(self.apply_feedback_label)

        self._apply_feedback_timer = QTimer(self)
        self._apply_feedback_timer.setSingleShot(True)
        self._apply_feedback_timer.setInterval(1800)
        self._apply_feedback_timer.timeout.connect(self.apply_feedback_label.hide)

        self.apply_btn = SecondaryButton("Apply")
        self.apply_btn.setAutoDefault(False)
        self.apply_btn.setMinimumWidth(72)
        self.apply_btn.setToolTip("Apply changes without closing Settings")
        self.apply_btn.clicked.connect(self._apply_live)
        layout.addWidget(self.apply_btn)

        self.cancel_btn = SecondaryButton("Close")
        self.cancel_btn.setAutoDefault(False)
        self.cancel_btn.setMinimumWidth(78)
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn)

        self.save_btn = PrimaryButton("Save")
        self.save_btn.setAutoDefault(False)
        self.save_btn.setMinimumWidth(72)
        self.save_btn.setToolTip("Save changes and close Settings")
        self.save_btn.clicked.connect(self.accept)
        layout.addWidget(self.save_btn)
        return footer

    # ── Page & Card Helpers ─────────────────────────────────────────────

    def _add_category(self, icon_name: str, label: str) -> int:
        item = QListWidgetItem(qta.icon(icon_name, color="#475569"), label)
        self.category_list.addItem(item)
        return self.category_list.count() - 1

    def _create_page(self, page_idx: int, title: str, subtitle: str):
        scroll = QScrollArea()
        scroll.setObjectName("settingsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setObjectName("settingsScrollContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(12)

        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 6)
        header_layout.setSpacing(3)

        lbl = QLabel(title)
        lbl.setObjectName("settingsPageTitle")
        header_layout.addWidget(lbl)

        sub = QLabel(subtitle)
        sub.setObjectName("settingsPageSubtitle")
        sub.setWordWrap(True)
        header_layout.addWidget(sub)

        divider = QFrame()
        divider.setObjectName("settingsHeaderDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        header_layout.addWidget(divider)
        layout.addWidget(header)

        scroll.setWidget(container)
        self._page_cards[page_idx] = []
        return scroll, layout

    def _create_card(self, page_idx: int, page_layout: QVBoxLayout, title: str) -> dict:
        section_lbl = QLabel(title.upper())
        section_lbl.setObjectName("settingsCardTitle")
        page_layout.addWidget(section_lbl)

        card = QFrame()
        card.setObjectName("settingsCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        page_layout.addWidget(card)

        card_info = {
            "page_idx": page_idx,
            "title_label": section_lbl,
            "card": card,
            "layout": card_layout,
            "rows": [],
        }
        self._page_cards[page_idx].append(card_info)
        return card_info

    def _add_row(
        self,
        card_info: dict,
        title: str,
        description: str,
        control: QWidget,
        control_width: int | None = 230,
    ) -> QWidget:
        card_layout = card_info["layout"]
        rows = card_info["rows"]

        divider = None
        if rows:
            divider = QFrame()
            divider.setObjectName("settingsRowDivider")
            divider.setFrameShape(QFrame.Shape.HLine)
            card_layout.addWidget(divider)

        row_widget = QWidget()
        row_widget.setObjectName("settingsRow")
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(14, 10, 14, 10)
        row_layout.setSpacing(14)

        text_box = QWidget()
        text_layout = QVBoxLayout(text_box)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("settingsRowTitle")
        title_lbl.setWordWrap(True)
        text_layout.addWidget(title_lbl)

        if description:
            desc_lbl = QLabel(description)
            desc_lbl.setObjectName("settingsRowDesc")
            desc_lbl.setWordWrap(True)
            text_layout.addWidget(desc_lbl)

        row_layout.addWidget(text_box, stretch=1)

        if control_width is not None and not isinstance(control, ToggleSwitch):
            control.setMaximumWidth(control_width)
            control.setMinimumWidth(min(140, control_width))
        row_layout.addWidget(control, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        card_layout.addWidget(row_widget)
        self._wire_dirty_signal(control)

        entry = {
            "page_idx": card_info["page_idx"],
            "title_lower": title.lower(),
            "desc_lower": (description or "").lower(),
            "row": row_widget,
            "divider": divider,
            "card_info": card_info,
        }
        rows.append(entry)
        self._search_entries.append(entry)
        return row_widget

    def _wire_dirty_signal(self, control: QWidget) -> None:
        if isinstance(control, QCheckBox):
            control.toggled.connect(self._mark_dirty)
        elif isinstance(control, QComboBox):
            control.currentIndexChanged.connect(self._mark_dirty)
        elif isinstance(control, QSpinBox):
            control.valueChanged.connect(self._mark_dirty)
        elif isinstance(control, QLineEdit):
            control.textChanged.connect(self._mark_dirty)
        else:
            for line_edit in control.findChildren(QLineEdit):
                line_edit.textChanged.connect(self._mark_dirty)

    def has_pending_changes(self) -> bool:
        """Return True if current UI values differ from the saved baseline."""
        return self.get_settings() != self._baseline_settings

    def _sync_footer_state(self) -> None:
        if self._is_initializing:
            return
        current = self.get_settings()
        has_changes = current != self._baseline_settings
        at_defaults = current == self._default_settings

        if hasattr(self, "apply_btn"):
            self.apply_btn.setEnabled(has_changes)
        if hasattr(self, "save_btn"):
            self.save_btn.setEnabled(True)
        if hasattr(self, "cancel_btn"):
            self.cancel_btn.setText("Cancel" if has_changes else "Close")
            self.cancel_btn.setToolTip(
                "Discard unapplied changes and close" if has_changes else "Close Settings"
            )
        if hasattr(self, "reset_btn"):
            self.reset_btn.setEnabled(not at_defaults)
        if hasattr(self, "category_list"):
            for page_idx, keys in self._page_setting_keys.items():
                item = self.category_list.item(page_idx)
                if item is not None:
                    dirty = any(current.get(k) != self._baseline_settings.get(k) for k in keys)
                    item.setData(Qt.ItemDataRole.UserRole, dirty)
            self.category_list.viewport().update()

    def _mark_dirty(self, *_args) -> None:
        if self._is_initializing:
            return
        self._sync_footer_state()
        if self.has_pending_changes():
            if hasattr(self, "_apply_feedback_timer"):
                self._apply_feedback_timer.stop()
            if hasattr(self, "apply_feedback_label"):
                self.apply_feedback_label.hide()

    def _apply_live(self) -> None:
        current = self.get_settings()
        self.settings_applied.emit(current)
        self._baseline_settings = current
        self._sync_footer_state()
        if hasattr(self, "apply_feedback_label"):
            self.apply_feedback_label.show()
        if hasattr(self, "_apply_feedback_timer"):
            self._apply_feedback_timer.start()

    def _on_category_changed(self, row: int) -> None:
        if 0 <= row < self.pages_stack.count():
            self.pages_stack.setCurrentIndex(row)

    def _filter_settings(self, query: str) -> None:
        needle = query.strip().lower()
        matching_pages: set[int] = set()

        for card_list in self._page_cards.values():
            for card_info in card_list:
                visible_in_card = 0
                for entry in card_info["rows"]:
                    matched = (
                        not needle
                        or needle in entry["title_lower"]
                        or needle in entry["desc_lower"]
                    )
                    entry["row"].setVisible(matched)
                    if entry["divider"] is not None:
                        entry["divider"].setVisible(matched and visible_in_card > 0)
                    if matched:
                        visible_in_card += 1
                        matching_pages.add(entry["page_idx"])
                card_visible = visible_in_card > 0 or not needle
                card_info["title_label"].setVisible(card_visible)
                card_info["card"].setVisible(card_visible)

        first_match = None
        for idx in range(self.category_list.count()):
            item = self.category_list.item(idx)
            has_match = not needle or idx in matching_pages
            item.setHidden(not has_match)
            if has_match and first_match is None:
                first_match = idx

        has_any = first_match is not None
        self.pages_stack.setVisible(has_any)
        self.search_empty_label.setVisible(not has_any)
        current_idx = self.category_list.currentRow()
        if has_any and (current_idx < 0 or self.category_list.item(current_idx).isHidden()):
            self.category_list.setCurrentRow(first_match)

    def _create_combo(self, items: list[str] | None = None) -> QComboBox:
        combo = QComboBox(self)
        combo.setStyleSheet("combobox-popup: 0;")
        view = QListView()
        view.setMinimumHeight(24)
        combo.setView(view)
        if items:
            combo.addItems(items)
        return combo

    def _create_path_picker(self, value: str, placeholder: str, handler) -> tuple[QWidget, QLineEdit]:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        edit = QLineEdit()
        edit.setText(value)
        edit.setPlaceholderText(placeholder)
        browse_btn = SecondaryButton("Browse...")
        browse_btn.clicked.connect(handler)

        layout.addWidget(edit, stretch=1)
        layout.addWidget(browse_btn)
        return wrapper, edit

    # ── Page Builders ───────────────────────────────────────────────────

    def _build_general_page(self) -> None:
        idx = self._add_category("fa5s.sliders-h", "General")
        scroll, layout = self._create_page(
            idx, "General Settings", "Configure visual theme, default connection, and startup behavior."
        )

        appearance = self._create_card(idx, layout, "Appearance & Startup")
        self.theme_combo = self._create_combo(["Grey (Default)", "Light Blue", "Light Green"])
        saved_theme = getattr(self.main_window, "theme", "Grey (Default)")
        theme_idx = self.theme_combo.findText(saved_theme)
        if theme_idx >= 0:
            self.theme_combo.setCurrentIndex(theme_idx)
        self._add_row(appearance, "Theme", "Application color theme.", self.theme_combo)

        self.default_conn_combo = self._create_combo()
        self.default_conn_combo.addItem("None (First Available)", None)
        try:
            import db

            for conn in db.get_all_connections_from_db():
                if is_connection_type_enabled(self.main_window, conn.get("code")):
                    self.default_conn_combo.addItem(conn["display_name"], conn["id"])
        except Exception as e:
            print(f"Error loading connections for preferences: {e}")

        saved_default_id = getattr(self.main_window, "default_connection_id", None)
        if saved_default_id is not None:
            conn_idx = self.default_conn_combo.findData(saved_default_id)
            if conn_idx >= 0:
                self.default_conn_combo.setCurrentIndex(conn_idx)
        self._add_row(
            appearance,
            "Default Connection",
            "Pre-selected connection when opening a new SQL worksheet.",
            self.default_conn_combo,
        )

        self.confirm_tab_close_check = ToggleSwitch()
        self.confirm_tab_close_check.setChecked(getattr(self.main_window, "confirm_tab_close", True))
        self._add_row(
            appearance,
            "Confirm Before Closing Tabs",
            "Ask for confirmation when closing worksheets with unsaved changes.",
            self.confirm_tab_close_check,
        )

        self.restore_session_check = ToggleSwitch()
        self.restore_session_check.setChecked(getattr(self.main_window, "restore_session_on_startup", True))
        self._add_row(
            appearance,
            "Restore Session on Startup",
            "Reopen previous tabs and window layout on launch.",
            self.restore_session_check,
        )

        self._page_setting_keys[idx] = (
            "theme",
            "default_connection_id",
            "confirm_tab_close",
            "restore_session_on_startup",
        )
        layout.addStretch()
        self.pages_stack.addWidget(scroll)

    def _build_features_page(self) -> None:
        idx = self._add_category("fa5s.cubes", "Features")
        scroll, layout = self._create_page(
            idx,
            "Features & Capabilities",
            "Enable or disable workspace modules and database connectors. Disabled items are hidden from menus and toolbars.",
        )

        preset_bar = QHBoxLayout()
        preset_bar.setContentsMargins(0, 0, 0, 2)
        preset_bar.setSpacing(8)
        enable_all_btn = SecondaryButton("Enable All Features")
        enable_all_btn.clicked.connect(lambda: self._set_all_feature_checks(True))
        core_only_btn = SecondaryButton("Core SQL Only")
        core_only_btn.setToolTip("Keep only SQL worksheets, results grid, PostgreSQL, and SQLite.")
        core_only_btn.clicked.connect(lambda: self._set_all_feature_checks(False))
        preset_bar.addWidget(enable_all_btn)
        preset_bar.addWidget(core_only_btn)
        preset_bar.addStretch()
        layout.addLayout(preset_bar)

        current_flags = normalize_feature_flags(getattr(self.main_window, "feature_flags", None))
        cards_by_cat: dict[str, dict] = {}
        for spec in FEATURE_CATALOG:
            if spec.category not in cards_by_cat:
                cards_by_cat[spec.category] = self._create_card(idx, layout, spec.category)
            toggle = ToggleSwitch()
            toggle.setChecked(current_flags.get(spec.key, spec.default_enabled))
            self.feature_checks[spec.key] = toggle
            self._add_row(cards_by_cat[spec.category], spec.name, spec.description, toggle)

        note_lbl = QLabel(
            "Core SQL worksheets, the results grid, PostgreSQL, and SQLite remain enabled. "
            "Turning off a connector hides it without deleting saved connections."
        )
        note_lbl.setObjectName("settingsNoteLabel")
        note_lbl.setWordWrap(True)
        layout.addWidget(note_lbl)

        self._page_setting_keys[idx] = ("feature_flags",)
        layout.addStretch()
        self.pages_stack.addWidget(scroll)

    def _set_all_feature_checks(self, enabled: bool) -> None:
        for toggle in self.feature_checks.values():
            toggle.setChecked(enabled)

    def _build_editor_page(self) -> None:
        idx = self._add_category("fa5s.code", "Text Editor")
        scroll, layout = self._create_page(
            idx, "Text Editor", "Configure font, layout, IntelliSense, and SQL formatting style."
        )

        typo = self._create_card(idx, layout, "Typography & View")
        self.editor_font_combo = QFontComboBox(self)
        self.editor_font_combo.setStyleSheet("combobox-popup: 0;")
        self.editor_font_combo.setView(QListView())
        self.editor_font_combo.setItemDelegate(FontPreviewDelegate(self.editor_font_combo))
        self.editor_font_combo.setMaxVisibleItems(15)
        self.editor_font_combo.setFontFilters(QFontComboBox.FontFilter.MonospacedFonts)
        self.editor_font_combo.setCurrentFont(QFont(getattr(self.main_window, "editor_font_family", "Consolas")))
        self._add_row(typo, "Font Family", "Monospaced typeface used in SQL query editors.", self.editor_font_combo)

        self.editor_font_size_spin = QSpinBox()
        self.editor_font_size_spin.setRange(8, 32)
        self.editor_font_size_spin.setValue(getattr(self.main_window, "editor_font_size", 10))
        self.editor_font_size_spin.setSuffix(" pt")
        self._add_row(typo, "Font Size", "Base font size in points (use Ctrl+Scroll to zoom).", self.editor_font_size_spin, 130)

        self.editor_tab_size_spin = QSpinBox()
        self.editor_tab_size_spin.setRange(2, 8)
        self.editor_tab_size_spin.setValue(getattr(self.main_window, "editor_tab_size", 4))
        self.editor_tab_size_spin.setSuffix(" spaces")
        self._add_row(typo, "Tab Size", "Spaces inserted per indentation level.", self.editor_tab_size_spin, 130)

        self.editor_word_wrap_check = ToggleSwitch()
        self.editor_word_wrap_check.setChecked(getattr(self.main_window, "editor_word_wrap", False))
        self._add_row(typo, "Word Wrap", "Wrap long lines to fit inside the editor viewport.", self.editor_word_wrap_check)

        self.editor_line_numbers_check = ToggleSwitch()
        self.editor_line_numbers_check.setChecked(getattr(self.main_window, "editor_line_numbers", True))
        self._add_row(typo, "Line Numbers", "Show line numbers in the left gutter.", self.editor_line_numbers_check)

        self.editor_highlight_line_check = ToggleSwitch()
        self.editor_highlight_line_check.setChecked(getattr(self.main_window, "editor_highlight_line", True))
        self._add_row(typo, "Highlight Active Line", "Highlight the line containing the cursor.", self.editor_highlight_line_check)

        editing = self._create_card(idx, layout, "IntelliSense & Editing")
        self.editor_autocomplete_check = ToggleSwitch()
        self.editor_autocomplete_check.setChecked(getattr(self.main_window, "editor_autocomplete", True))
        self._add_row(editing, "SQL Auto-Completion", "Suggest keywords, schemas, tables, and columns while typing.", self.editor_autocomplete_check)

        self.editor_auto_close_chars_check = ToggleSwitch()
        self.editor_auto_close_chars_check.setChecked(getattr(self.main_window, "editor_auto_close_chars", True))
        self._add_row(editing, "Auto-Close Brackets & Quotes", "Insert matching quotes and brackets automatically ('', \"\", (), [], {}).", self.editor_auto_close_chars_check)

        self.editor_auto_indent_check = ToggleSwitch()
        self.editor_auto_indent_check.setChecked(getattr(self.main_window, "editor_auto_indent", True))
        self._add_row(editing, "Auto-Indent on Enter", "Preserve indentation on new lines inside SQL and PL/SQL blocks.", self.editor_auto_indent_check)

        casing = self._create_card(idx, layout, "SQL Casing Style")
        self.editor_keyword_casing_combo = self._create_combo(["UPPERCASE", "lowercase", "Preserve (As-is)"])
        kw_idx = self.editor_keyword_casing_combo.findText(getattr(self.main_window, "editor_keyword_casing", "UPPERCASE"))
        if kw_idx >= 0:
            self.editor_keyword_casing_combo.setCurrentIndex(kw_idx)
        self._add_row(casing, "Keyword Casing", "Casing applied to SQL keywords (SELECT, FROM, WHERE) when formatting.", self.editor_keyword_casing_combo)

        self.editor_identifier_casing_combo = self._create_combo(["lowercase", "UPPERCASE", "Preserve (As-is)"])
        id_idx = self.editor_identifier_casing_combo.findText(getattr(self.main_window, "editor_identifier_casing", "Preserve (As-is)"))
        if id_idx >= 0:
            self.editor_identifier_casing_combo.setCurrentIndex(id_idx)
        self._add_row(casing, "Identifier Casing", "Casing applied to schema, table, and column names.", self.editor_identifier_casing_combo)

        self._page_setting_keys[idx] = (
            "editor_font_family",
            "editor_font_size",
            "editor_tab_size",
            "editor_word_wrap",
            "editor_line_numbers",
            "editor_highlight_line",
            "editor_autocomplete",
            "editor_auto_close_chars",
            "editor_auto_indent",
            "editor_keyword_casing",
            "editor_identifier_casing",
        )
        layout.addStretch()
        self.pages_stack.addWidget(scroll)

    def _build_results_view_page(self) -> None:
        idx = self._add_category("fa5s.table", "Results & Grid")
        scroll, layout = self._create_page(
            idx, "Results & Data Grid", "Configure query output tables, cell formatting, and clipboard behavior."
        )

        presentation = self._create_card(idx, layout, "Cell Presentation & Pagination")
        self.grid_null_text_edit = QLineEdit()
        self.grid_null_text_edit.setPlaceholderText("NULL")
        self.grid_null_text_edit.setText(getattr(self.main_window, "grid_null_text", "NULL"))
        self._add_row(presentation, "NULL Display Text", "Placeholder text rendered for SQL NULL values (for example, NULL or (null)).", self.grid_null_text_edit)

        self.grid_date_format_combo = self._create_combo([
            "YYYY-MM-DD HH:mm:ss",
            "ISO-8601 (YYYY-MM-DDTHH:mm:ss)",
            "MM/DD/YYYY HH:mm:ss",
            "DD/MM/YYYY HH:mm:ss",
            "Locale Default",
        ])
        dt_idx = self.grid_date_format_combo.findText(getattr(self.main_window, "grid_datetime_format", "YYYY-MM-DD HH:mm:ss"))
        if dt_idx >= 0:
            self.grid_date_format_combo.setCurrentIndex(dt_idx)
        self._add_row(presentation, "Timestamp Format", "Display format for date and timestamp columns.", self.grid_date_format_combo)

        self.grid_page_size_combo = self._create_combo(["50", "100", "200", "500", "1000", "All (No Pagination)"])
        ps_idx = self.grid_page_size_combo.findText(str(getattr(self.main_window, "grid_page_size", "100")))
        if ps_idx >= 0:
            self.grid_page_size_combo.setCurrentIndex(ps_idx)
        self._add_row(presentation, "Rows Per Page", "Default number of rows loaded per page in result grids.", self.grid_page_size_combo)

        behavior = self._create_card(idx, layout, "Grid & Clipboard")
        self.grid_show_row_numbers_check = ToggleSwitch()
        self.grid_show_row_numbers_check.setChecked(getattr(self.main_window, "grid_show_row_numbers", True))
        self._add_row(behavior, "Show Row Numbers", "Display 1-based row numbers along the left edge of result grids.", self.grid_show_row_numbers_check)

        self.grid_copy_headers_check = ToggleSwitch()
        self.grid_copy_headers_check.setChecked(getattr(self.main_window, "grid_copy_headers", True))
        self._add_row(behavior, "Include Column Headers on Copy", "Prepend column names when copying selected cells (Ctrl+C).", self.grid_copy_headers_check)

        self._page_setting_keys[idx] = (
            "grid_null_text",
            "grid_datetime_format",
            "grid_page_size",
            "grid_show_row_numbers",
            "grid_copy_headers",
        )
        layout.addStretch()
        self.pages_stack.addWidget(scroll)

    def _build_database_tools_page(self) -> None:
        idx = self._add_category("fa5s.database", "Database Tools")
        scroll, layout = self._create_page(
            idx, "Database Tools & Execution", "Configure CLI client binary paths and query execution limits."
        )

        binaries = self._create_card(idx, layout, "External CLI Binaries")

        # 1. PostgreSQL Binary Path (unified Windows + WSL dropdown)
        self.pg_bin_picker = BinaryPathSelector(
            current_val=getattr(self.main_window, "pg_bin_path", ""),
            candidates=get_all_postgres_candidates(),
            dialog_title="Select PostgreSQL Bin Directory",
            parent=self,
            use_wsl=bool(getattr(self.main_window, "use_wsl", False)),
            wsl_distro=getattr(self.main_window, "wsl_distro", None),
        )
        self.pg_bin_picker.path_changed.connect(lambda _p: self._mark_dirty())
        self._add_row(
            binaries,
            "PostgreSQL Binary Path",
            "Directory containing psql, pg_dump, and pg_restore executables.",
            self.pg_bin_picker,
            330,
        )

        # 2. Oracle Binary Path
        self.oracle_bin_picker = BinaryPathSelector(
            getattr(self.main_window, "oracle_bin_path", ""),
            get_sqlplus_candidates(),
            "Select Oracle Bin Directory",
            parent=self,
        )
        self.oracle_bin_picker.path_changed.connect(lambda _p: self._mark_dirty())
        self._add_row(
            binaries,
            "Oracle Binary Path",
            "Directory containing sqlplus and Oracle Instant Client libraries.",
            self.oracle_bin_picker,
            330,
        )

        execution = self._create_card(idx, layout, "Query Execution Limits")
        self.query_timeout_spin = QSpinBox()
        self.query_timeout_spin.setRange(5, 3600)
        self.query_timeout_spin.setValue(int(getattr(self.main_window, "query_timeout_sec", 300)))
        self.query_timeout_spin.setSuffix(" seconds")
        self._add_row(execution, "Query Timeout", "Automatically cancel running queries that exceed this limit.", self.query_timeout_spin, 150)

        self.default_row_limit_combo = self._create_combo(["No Limit", "100", "500", "1000", "5000"])
        lim_idx = self.default_row_limit_combo.findText(str(getattr(self.main_window, "default_row_limit", "No Limit")))
        if lim_idx >= 0:
            self.default_row_limit_combo.setCurrentIndex(lim_idx)
        self._add_row(execution, "Default Row Limit", "Maximum rows returned per query in new worksheets.", self.default_row_limit_combo)

        self._page_setting_keys[idx] = (
            "pg_bin_path",
            "oracle_bin_path",
            "use_wsl",
            "wsl_distro",
            "query_timeout_sec",
            "default_row_limit",
        )
        layout.addStretch()
        self.pages_stack.addWidget(scroll)

    def _build_ai_assistant_page(self) -> None:
        idx = self._add_category("fa5s.robot", "AI Assistant")
        scroll, layout = self._create_page(
            idx, "AI Assistant", "Configure AI models and endpoints for SQL explanation and chat."
        )

        card = self._create_card(idx, layout, "Model & Provider")
        self.ai_provider_combo = self._create_combo([
            "OpenAI",
            "Groq",
            "Google Gemini",
            "Anthropic Claude",
            "Ollama (Local)",
            "Custom (OpenAI-compatible)",
        ])
        prov_idx = self.ai_provider_combo.findText(getattr(self.main_window, "ai_provider", "OpenAI"))
        if prov_idx >= 0:
            self.ai_provider_combo.setCurrentIndex(prov_idx)
        self._add_row(card, "AI Provider", "LLM service or local runtime used for SQL explanations.", self.ai_provider_combo)

        self.ai_model_edit = QLineEdit()
        self.ai_model_edit.setText(getattr(self.main_window, "ai_model", ""))
        self.ai_model_edit.setPlaceholderText("e.g. gpt-4o-mini, gemini-1.5-flash")
        self._add_row(card, "Model Name", "Model identifier, or leave blank for the provider default.", self.ai_model_edit)

        self.ai_api_key_edit = PasswordBox()
        self.ai_api_key_edit.setText(getattr(self.main_window, "ai_api_key", ""))
        self.ai_api_key_edit.setPlaceholderText("sk-... (optional for local Ollama)")
        self._add_row(card, "API Key", "Stored locally in settings. Leave blank when using local Ollama.", self.ai_api_key_edit)

        self.ai_base_url_edit = QLineEdit()
        self.ai_base_url_edit.setText(getattr(self.main_window, "ai_base_url", ""))
        self.ai_base_url_edit.setPlaceholderText("https://api.groq.com/openai/v1 or http://localhost:11434/v1")
        self._add_row(card, "Base URL (Optional)", "Custom OpenAI-compatible API endpoint URL.", self.ai_base_url_edit, 290)

        self.ai_provider_combo.currentTextChanged.connect(self._on_ai_provider_changed)

        self._page_setting_keys[idx] = (
            "ai_provider",
            "ai_model",
            "ai_api_key",
            "ai_base_url",
        )
        layout.addStretch()
        self.pages_stack.addWidget(scroll)

    def _on_ai_provider_changed(self, text: str) -> None:
        if "Groq" in text:
            if not self.ai_base_url_edit.text():
                self.ai_base_url_edit.setPlaceholderText("https://api.groq.com/openai/v1")
            if not self.ai_model_edit.text():
                self.ai_model_edit.setPlaceholderText("llama-3.3-70b-versatile or qwen-qwq-32b")
        elif "Ollama" in text:
            if not self.ai_base_url_edit.text():
                self.ai_base_url_edit.setPlaceholderText("http://localhost:11434/v1")
            if not self.ai_model_edit.text():
                self.ai_model_edit.setPlaceholderText("qwen2.5-coder:14b or llama3")
        elif "Gemini" in text:
            if not self.ai_model_edit.text():
                self.ai_model_edit.setPlaceholderText("gemini-1.5-flash or gemini-2.0-flash")
        elif "Anthropic" in text:
            if not self.ai_model_edit.text():
                self.ai_model_edit.setPlaceholderText("claude-3-5-sonnet-20241022")
        else:
            if not self.ai_model_edit.text():
                self.ai_model_edit.setPlaceholderText("gpt-4o-mini")

    # ── Browse Handlers ─────────────────────────────────────────────────

    def browse_pg_bin(self) -> None:
        self.pg_bin_picker._on_browse_clicked()

    def browse_oracle_bin(self) -> None:
        self.oracle_bin_picker._on_browse_clicked()

    # ── Defaults & Values ───────────────────────────────────────────────

    def _build_default_settings(self) -> dict:
        default_font = (
            "Consolas"
            if self.editor_font_combo.findText("Consolas") >= 0
            else self.editor_font_combo.currentFont().family()
        )
        return {
            "theme": "Grey (Default)",
            "default_connection_id": None,
            "confirm_tab_close": True,
            "restore_session_on_startup": True,
            "feature_flags": {
                key: (FEATURE_SPEC_BY_KEY[key].default_enabled if key in FEATURE_SPEC_BY_KEY else True)
                for key in self.feature_checks
            },
            "editor_font_family": default_font,
            "editor_font_size": 10,
            "editor_tab_size": 4,
            "editor_word_wrap": False,
            "editor_line_numbers": True,
            "editor_autocomplete": True,
            "editor_highlight_line": True,
            "editor_keyword_casing": "UPPERCASE",
            "editor_identifier_casing": "Preserve (As-is)",
            "editor_auto_close_chars": True,
            "editor_auto_indent": True,
            "grid_null_text": "NULL",
            "grid_datetime_format": "YYYY-MM-DD HH:mm:ss",
            "grid_page_size": "100",
            "grid_show_row_numbers": True,
            "grid_copy_headers": True,
            "pg_bin_path": "",
            "oracle_bin_path": "",
            "use_wsl": False,
            "wsl_distro": None,
            "query_timeout_sec": 300,
            "default_row_limit": "No Limit",
            "ai_provider": "OpenAI",
            "ai_model": "",
            "ai_api_key": "",
            "ai_base_url": "",
        }

    def restore_defaults(self) -> None:
        """Restore all UI settings controls to recommended defaults."""
        defaults = self._default_settings or self._build_default_settings()
        self._is_initializing = True
        try:
            self.theme_combo.setCurrentText(defaults["theme"])
            self.default_conn_combo.setCurrentIndex(0)
            self.confirm_tab_close_check.setChecked(defaults["confirm_tab_close"])
            self.restore_session_check.setChecked(defaults["restore_session_on_startup"])

            self.editor_font_combo.setCurrentFont(QFont(defaults["editor_font_family"]))
            self.editor_font_size_spin.setValue(defaults["editor_font_size"])
            self.editor_tab_size_spin.setValue(defaults["editor_tab_size"])
            self.editor_word_wrap_check.setChecked(defaults["editor_word_wrap"])
            self.editor_line_numbers_check.setChecked(defaults["editor_line_numbers"])
            self.editor_autocomplete_check.setChecked(defaults["editor_autocomplete"])
            self.editor_highlight_line_check.setChecked(defaults["editor_highlight_line"])
            self.editor_keyword_casing_combo.setCurrentText(defaults["editor_keyword_casing"])
            self.editor_identifier_casing_combo.setCurrentText(defaults["editor_identifier_casing"])
            self.editor_auto_close_chars_check.setChecked(defaults["editor_auto_close_chars"])
            self.editor_auto_indent_check.setChecked(defaults["editor_auto_indent"])

            self.grid_null_text_edit.setText(defaults["grid_null_text"])
            self.grid_date_format_combo.setCurrentText(defaults["grid_datetime_format"])
            self.grid_page_size_combo.setCurrentText(defaults["grid_page_size"])
            self.grid_show_row_numbers_check.setChecked(defaults["grid_show_row_numbers"])
            self.grid_copy_headers_check.setChecked(defaults["grid_copy_headers"])

            self.pg_bin_picker.set_selected_info(
                pg_bin_path=defaults["pg_bin_path"],
                use_wsl=defaults.get("use_wsl", False),
                wsl_distro=defaults.get("wsl_distro", None),
            )
            self.oracle_bin_picker.set_value(defaults["oracle_bin_path"])
            self.query_timeout_spin.setValue(defaults["query_timeout_sec"])
            self.default_row_limit_combo.setCurrentText(defaults["default_row_limit"])

            self.ai_provider_combo.setCurrentText(defaults["ai_provider"])
            self.ai_model_edit.setText(defaults["ai_model"])
            self.ai_api_key_edit.setText(defaults["ai_api_key"])
            self.ai_base_url_edit.setText(defaults["ai_base_url"])

            for key, toggle in self.feature_checks.items():
                toggle.setChecked(defaults["feature_flags"].get(key, True))
        finally:
            self._is_initializing = False
        self._mark_dirty()

    def get_settings(self) -> dict:
        """Return dictionary of all current settings values."""
        pg_info = self.pg_bin_picker.get_selected_info()
        return {
            "theme": self.theme_combo.currentText(),
            "default_connection_id": self.default_conn_combo.currentData(),
            "confirm_tab_close": self.confirm_tab_close_check.isChecked(),
            "restore_session_on_startup": self.restore_session_check.isChecked(),
            "feature_flags": {
                key: toggle.isChecked()
                for key, toggle in self.feature_checks.items()
            },
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
            "grid_null_text": self.grid_null_text_edit.text(),
            "grid_datetime_format": self.grid_date_format_combo.currentText(),
            "grid_page_size": self.grid_page_size_combo.currentText(),
            "grid_show_row_numbers": self.grid_show_row_numbers_check.isChecked(),
            "grid_copy_headers": self.grid_copy_headers_check.isChecked(),
            "pg_bin_path": pg_info["pg_bin_path"],
            "oracle_bin_path": self.oracle_bin_picker.get_value(),
            "use_wsl": pg_info["use_wsl"],
            "wsl_distro": pg_info["wsl_distro"],
            "query_timeout_sec": self.query_timeout_spin.value(),
            "default_row_limit": self.default_row_limit_combo.currentText(),
            "ai_provider": self.ai_provider_combo.currentText(),
            "ai_model": self.ai_model_edit.text().strip(),
            "ai_api_key": self.ai_api_key_edit.text().strip(),
            "ai_base_url": self.ai_base_url_edit.text().strip(),
        }


SettingsDialog = PreferencesDialog
