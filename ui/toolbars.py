import qtawesome as qta
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QAction, QFont
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QButtonGroup, 
    QToolButton, QComboBox, QMenu, QLabel, QListView
)
from ui.components import IconButton, SearchBox, ActionToolButton, DropdownToolButton

class NavigationHeader(QWidget):
    """
    A reusable tab-like header for switching between stacked views.
    Used for ResultsHeader and EditorHeader.
    """
    tab_switched = Signal(int)

    def __init__(self, object_name, tabs, parent=None):
        """
        :param object_name: string for QSS styling (e.g., 'resultsHeader')
        :param tabs: list of tuples (label, minimum_width, id_index)
        """
        super().__init__(parent)
        self.setObjectName(object_name)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 1)
        layout.setSpacing(4)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        self.buttons = {}
        first_btn = None

        for label, min_width, idx in tabs:
            btn = QPushButton(label)
            btn.setMinimumWidth(min_width)
            btn.setCheckable(True)
            self.button_group.addButton(btn, idx)
            layout.addWidget(btn)
            self.buttons[idx] = btn
            if first_btn is None:
                first_btn = btn

        layout.addStretch()

        if first_btn:
            first_btn.setChecked(True)

        self.button_group.idClicked.connect(self.tab_switched.emit)

    def get_button(self, idx):
        return self.buttons.get(idx)


class WorksheetToolbar(QWidget):
    """
    The main action toolbar for the Worksheet editor.
    """
    limit_changed = Signal(str)

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setObjectName("tab_toolbar")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)

        # Open
        self.open_btn = QToolButton()
        self.open_btn.setDefaultAction(manager.ws_open_file_action)
        self.open_btn.setIconSize(QSize(16, 16))
        self.open_btn.setFixedHeight(30)
        self.open_btn.setMinimumWidth(26)
        self.open_btn.setToolTip("Open SQL File")
        layout.addWidget(self.open_btn)

        # Save
        self.save_btn = QToolButton()
        self.save_btn.setDefaultAction(manager.ws_save_as_action)
        self.save_btn.setIconSize(QSize(16, 16))
        self.save_btn.setFixedHeight(30)
        self.save_btn.setMinimumWidth(26)
        self.save_btn.setToolTip("Save SQL File")
        layout.addWidget(self.save_btn)

        layout.addWidget(manager.create_vertical_separator())

        # Execute
        self.exec_btn = QToolButton()
        self.exec_btn.setDefaultAction(manager.ws_execute_action)
        self.exec_btn.setIconSize(QSize(16, 16))
        self.exec_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.exec_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        exec_menu = QMenu(self.exec_btn)
        exec_menu.addAction(manager.ws_execute_new_tab_action)
        self.exec_btn.setMenu(exec_menu)
        self.exec_btn.setFixedHeight(30)
        layout.addWidget(self.exec_btn)

        # Cancel
        self.cancel_btn = QToolButton()
        self.cancel_btn.setDefaultAction(manager.ws_cancel_action)
        self.cancel_btn.setIconSize(QSize(16, 16))
        self.cancel_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.cancel_btn.setFixedHeight(30)
        layout.addWidget(self.cancel_btn)

        # Explain
        self.explain_combo = ActionToolButton("Explain Analyze", QIcon("assets/explain_icon.png"))
        self.explain_combo.setFixedWidth(135)
        self.explain_combo.addItem("Explain Analyze", QIcon("assets/explain_icon.png"))
        self.explain_combo.addItem("Explain (Plan)", QIcon("assets/explain_icon.png"))
        self.explain_combo.itemTriggered.connect(self._on_explain_triggered)
        layout.addWidget(self.explain_combo)

        # Edit Menu
        self.edit_btn = QToolButton()
        self.edit_btn.setText("Edit")
        self.edit_btn.setIcon(qta.icon("fa5s.edit"))
        self.edit_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.edit_btn.setFixedHeight(30)
        self.edit_btn.setFixedWidth(85)
        self.edit_btn.setToolTip("Edit Operations")
        self.edit_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        edit_menu = QMenu(self)
        self._populate_edit_menu(edit_menu)
        self.edit_btn.setMenu(edit_menu)
        layout.addWidget(self.edit_btn)

        layout.addWidget(manager.create_vertical_separator())

        # Rows Limit
        rows_label = QLabel("Limit:")
        layout.addWidget(rows_label)

        self.rows_limit_combo = DropdownToolButton("No Limit")
        self.rows_limit_combo.setObjectName("rows_limit_combo")
        self.rows_limit_combo.setFixedWidth(90)
        self.rows_limit_combo.addItems(["No Limit", "100", "500", "1000"])
        self.rows_limit_combo.itemTriggered.connect(
            lambda text: self.limit_changed.emit(text)
        )
        layout.addWidget(self.rows_limit_combo)

        layout.addWidget(manager.create_vertical_separator())
        layout.addStretch()

    def _on_explain_triggered(self, text):
        if text == "Explain Analyze":
            self.manager.explain_query()
        else:
            self.manager.explain_plan_query()

    def _populate_edit_menu(self, edit_menu):
        mgr = self.manager
        
        edit_menu.addAction(mgr.ws_undo_action)
        edit_menu.addAction(mgr.ws_redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(mgr.ws_cut_action)
        edit_menu.addAction(mgr.ws_copy_action)
        edit_menu.addAction(mgr.ws_paste_action)
        edit_menu.addAction(mgr.ws_select_all_action)
        edit_menu.addSeparator()
        edit_menu.addAction(mgr.ws_find_action)
        edit_menu.addAction(mgr.ws_replace_action)
        edit_menu.addAction(mgr.ws_goto_line_action)
        edit_menu.addSeparator()
        edit_menu.addAction(mgr.ws_comment_block_action)
        edit_menu.addAction(mgr.ws_uncomment_block_action)
        edit_menu.addAction(mgr.ws_upper_case_action)
        edit_menu.addAction(mgr.ws_lower_case_action)
        edit_menu.addAction(mgr.ws_initial_caps_action)
        edit_menu.addSeparator()
        edit_menu.addAction(mgr.ws_clear_all_action)
        edit_menu.addAction(mgr.ws_format_sql_action)

class ResultsInfoToolbar(QWidget):
    """
    Toolbar for Results View (add/save/delete rows, search, pagination).
    """
    def __init__(self, manager, tab_content, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.tab_content = tab_content
        self.setObjectName("resultsInfoBar")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)

        # Row Actions
        self.add_row_btn = IconButton(qta.icon("ri.play-list-add-fill", color="#555555"), "Add new row")
        self.add_row_btn.setObjectName("add_row_btn")
        self.add_row_btn.clicked.connect(manager.add_empty_row)
        layout.addWidget(self.add_row_btn)

        self.save_row_btn = IconButton(qta.icon("fa5s.save", color="#555555"), "Save new row")
        self.save_row_btn.setObjectName("save_row_btn")
        self.save_row_btn.clicked.connect(manager.save_new_row)
        layout.addWidget(self.save_row_btn)

        self.delete_row_btn = IconButton(qta.icon("fa5s.trash-alt", color="#dc3545"), "Delete selected row(s)")
        self.delete_row_btn.setObjectName("delete_row_btn")
        self.delete_row_btn.clicked.connect(manager.delete_selected_row)
        layout.addWidget(self.delete_row_btn)

        self.copy_btn = IconButton(qta.icon("fa5s.copy", color="#555555"), "Copy selected cells (Ctrl+C)")
        self.copy_btn.clicked.connect(manager.copy_current_result_table)
        layout.addWidget(self.copy_btn)

        self.download_btn = IconButton(qta.icon("fa5s.file-download", color="#555555"), "Download query result")
        self.download_btn.clicked.connect(lambda: manager.download_result(self.tab_content))
        layout.addWidget(self.download_btn)

        # Table Search
        self.search_box = SearchBox()
        self.search_box.setFixedHeight(28)
        self.search_box.setFixedWidth(180)
        self.search_box.setObjectName("table_search_box")
        self.search_box.hide()
        self.search_box.installEventFilter(manager)

        self.table_search_btn = IconButton(qta.icon("fa5s.search", color="#555555"), "Search in Results")
        self.table_search_btn.setObjectName("table_search_btn")
        self.table_search_btn.clicked.connect(manager.toggle_table_search)

        self.search_debounce_timer = QTimer(self)
        self.search_debounce_timer.setInterval(300)
        self.search_debounce_timer.setSingleShot(True)
        self.search_debounce_timer.timeout.connect(self._trigger_filter)
        self.search_box.textChanged.connect(self._on_search_text_changed)

        layout.addWidget(self.search_box)
        layout.addWidget(self.table_search_btn)
        
        layout.addStretch()

        # Pagination and Limit Info
        self.rows_info_label = QLabel("Showing Rows")
        self.rows_info_label.setObjectName("rows_info_label")
        font = QFont()
        font.setBold(True)
        self.rows_info_label.setFont(font)
        layout.addWidget(self.rows_info_label)

        self.rows_setting_btn = IconButton(qta.icon("fa5s.list-ul", color="#555555"), "Edit Limit/Offset")
        self.rows_setting_btn.clicked.connect(lambda: manager.open_limit_offset_dialog(self.tab_content))
        layout.addWidget(self.rows_setting_btn)

        # Navigation Buttons Container
        nav_container = QWidget()
        nav_container.setObjectName("navContainer")
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(6)

        arrow_font = QFont("Segoe UI", 16, QFont.Weight.Bold)

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedSize(30, 28)
        self.prev_btn.setFont(arrow_font)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setObjectName("prev_btn")
        self.prev_btn.clicked.connect(self._go_prev)
        
        self.page_label = QLabel("Page 1")
        self.page_label.setMinimumWidth(60)
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setFont(QFont("Segoe UI", 9))
        self.page_label.setObjectName("page_label")

        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedSize(30, 28)
        self.next_btn.setFont(arrow_font)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setObjectName("next_btn")
        self.next_btn.clicked.connect(self._go_next)

        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.page_label)
        nav_layout.addWidget(self.next_btn)
        
        layout.addWidget(nav_container)
        self.hide() # Hidden by default

    def _trigger_filter(self):
        current_table = self.manager._get_result_table_for_tab(self.tab_content)
        if current_table:
            current_model = current_table.model()
            if hasattr(current_model, "setFilterFixedString"):
                current_model.setFilterFixedString(self.search_box.text())

    def _on_search_text_changed(self, text):
        self.search_debounce_timer.stop()
        self.search_debounce_timer.start()
        
    def _go_prev(self):
        tab = self.tab_content
        if not tab or getattr(tab, "current_page", 1) <= 1:
            return
        tab.current_page -= 1
        tab.current_offset = (tab.current_page - 1) * getattr(tab, "current_limit", 0)
        self.update_page_ui(tab)
        self.manager.main_window.worksheet_manager.execute_query(preserve_pagination=True)

    def _go_next(self):
        tab = self.tab_content
        if not getattr(tab, "has_more_pages", False):
            return
        tab.current_page = getattr(tab, "current_page", 1) + 1
        tab.current_offset = (tab.current_page - 1) * getattr(tab, "current_limit", 0)
        self.update_page_ui(tab)
        self.manager.main_window.worksheet_manager.execute_query(preserve_pagination=True)

    def update_page_ui(self, tab=None):
        tab = tab or self.tab_content
        self.page_label.setText(f"Page {getattr(tab, 'current_page', 1)}")
        self.prev_btn.setEnabled(getattr(tab, 'current_page', 1) > 1)

        limit = getattr(tab, "current_limit", 0)
        offset = getattr(tab, "current_offset", 0)
        if limit and limit > 0:
            self.rows_info_label.setText(f"Limit: {limit} | Offset: {offset}")
        else:
            self.rows_info_label.setText("No Limit")


class ProcessFilterBar(QWidget):
    """
    Toolbar for filtering processes in the Processes View.
    """
    def __init__(self, manager, tab_content, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.tab_content = tab_content
        self.setObjectName("processFilterBar")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        filters = [
            ("All (0)", "ALL"),
            ("Running (0)", "RUNNING"),
            ("Successful (0)", "SUCCESSFUL"),
            ("Warning (0)", "WARNING"),
            ("Error (0)", "ERROR")
        ]

        self.filter_buttons = {}
        for label, filter_id in filters:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setMinimumWidth(84)
            layout.addWidget(btn)
            self.button_group.addButton(btn)
            self.filter_buttons[filter_id] = btn
            # using default argument in lambda to capture filter_id
            btn.clicked.connect(lambda checked=False, fid=filter_id: self.manager._set_process_filter(self.tab_content, fid))

        self.filter_buttons["ALL"].setChecked(True)
        self.tab_content.process_filter_buttons = self.filter_buttons

        layout.addStretch()
        
        # Search Field
        self.search_edit = SearchBox("Search processes...")
        self.search_edit.setFixedWidth(150)
        self.search_edit.textChanged.connect(lambda text: self.manager._filter_processes_table(self.tab_content, text))
        layout.addWidget(self.search_edit)
        
        # View Log Button
        self.view_log_btn = QPushButton(qta.icon("fa5s.file-alt"), "View Log")
        self.view_log_btn.clicked.connect(lambda: self.manager._handle_view_log(self.tab_content))
        layout.addWidget(self.view_log_btn)

        self.refresh_now_btn = QPushButton("Refresh")
        self.refresh_now_btn.setObjectName("process_refresh_now_btn")
        self.refresh_now_btn.setFixedHeight(28)
        self.refresh_now_btn.setMinimumWidth(76)
        self.refresh_now_btn.clicked.connect(self.manager.refresh_processes_view)
        layout.addWidget(self.refresh_now_btn)

        self.hide() # Hidden by default
