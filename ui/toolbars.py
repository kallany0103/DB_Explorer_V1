import qtawesome as qta
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QButtonGroup, 
    QToolButton, QMenu, QLabel, QPushButton, QFrame,
    QStyleOption, QStyle
)
from ui.components import (
    IconButton, SearchBox, ActionToolButton, DropdownToolButton,
    NavigationTabButton, ToolbarActionButton, CompactButton
)




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
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(34)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 2)
        layout.setSpacing(4)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        self.buttons = {}
        first_btn = None

        for label, min_width, idx in tabs:
            btn = NavigationTabButton(label)
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

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        super().paintEvent(event)


class WorksheetToolbar(QWidget):
    """
    The main action toolbar for the Worksheet editor.
    """
    limit_changed = Signal(str)

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setObjectName("tab_toolbar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)

        # Open
        self.open_btn = ToolbarActionButton(icon=manager.ws_open_file_action.icon())
        self.open_btn.setDefaultAction(manager.ws_open_file_action)
        self.open_btn.setIconSize(QSize(16, 16))
        self.open_btn.setMinimumWidth(32)
        self.open_btn.setToolTip("Open SQL File")
        layout.addWidget(self.open_btn)

        # Save
        self.save_btn = ToolbarActionButton(icon=manager.ws_save_as_action.icon())
        self.save_btn.setDefaultAction(manager.ws_save_as_action)
        self.save_btn.setIconSize(QSize(16, 16))
        self.save_btn.setMinimumWidth(32)
        self.save_btn.setToolTip("Save SQL File")
        layout.addWidget(self.save_btn)

        layout.addWidget(manager.create_vertical_separator())

        # Execute
        self.exec_btn = ToolbarActionButton(icon=manager.ws_execute_action.icon())
        self.exec_btn.setDefaultAction(manager.ws_execute_action)
        self.exec_btn.setIconSize(QSize(16, 16))
        self.exec_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        exec_menu = QMenu(self.exec_btn)
        exec_menu.addAction(manager.ws_execute_new_tab_action)
        self.exec_btn.setMenu(exec_menu)
        self.exec_btn.setFixedWidth(48)
        layout.addWidget(self.exec_btn)

        # Cancel
        self.cancel_btn = ToolbarActionButton(icon=manager.ws_cancel_action.icon())
        self.cancel_btn.setDefaultAction(manager.ws_cancel_action)
        self.cancel_btn.setIconSize(QSize(16, 16))
        self.cancel_btn.setMinimumWidth(32)
        layout.addWidget(self.cancel_btn)
        layout.addWidget(manager.create_vertical_separator())

        # Auto-Commit
        self.auto_commit_btn = ToolbarActionButton(icon=manager.ws_autocommit_action.icon())
        self.auto_commit_btn.setDefaultAction(manager.ws_autocommit_action)
        self.auto_commit_btn.setIconSize(QSize(16, 16))
        self.auto_commit_btn.setMinimumWidth(32)
        self.auto_commit_btn.setToolTip("Auto-Commit")
        layout.addWidget(self.auto_commit_btn)

        # Commit
        self.commit_btn = ToolbarActionButton(icon=manager.ws_commit_action.icon())
        self.commit_btn.setDefaultAction(manager.ws_commit_action)
        self.commit_btn.setIconSize(QSize(16, 16))
        self.commit_btn.setMinimumWidth(32)
        self.commit_btn.setToolTip("Commit Transaction")
        layout.addWidget(self.commit_btn)

        # Rollback
        self.rollback_btn = ToolbarActionButton(icon=manager.ws_rollback_action.icon())
        self.rollback_btn.setDefaultAction(manager.ws_rollback_action)
        self.rollback_btn.setIconSize(QSize(16, 16))
        self.rollback_btn.setMinimumWidth(32)
        self.rollback_btn.setToolTip("Rollback Transaction")
        layout.addWidget(self.rollback_btn)

        layout.addWidget(manager.create_vertical_separator())

        self.explain_combo = ActionToolButton("", qta.icon("fa5s.stopwatch", color="#555555"))
        self.explain_combo.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.explain_combo.setFixedWidth(48)
        self.explain_combo.setToolTip("Explain Query")
        self.explain_combo.addItem("Explain Analyze", qta.icon("fa5s.stopwatch", color="#555555"))
        self.explain_combo.addItem("Explain (Plan)", qta.icon("fa5s.stopwatch", color="#555555"))
        self.explain_combo.itemTriggered.connect(self._on_explain_triggered)
        layout.addWidget(self.explain_combo)

        # Explain code using AI button (Toad style)
        if hasattr(manager, 'ws_explain_ai_action'):
            self.explain_ai_btn = ToolbarActionButton(icon=manager.ws_explain_ai_action.icon())
            self.explain_ai_btn.setDefaultAction(manager.ws_explain_ai_action)
            self.explain_ai_btn.setIconSize(QSize(16, 16))
            self.explain_ai_btn.setMinimumWidth(32)
            self.explain_ai_btn.setToolTip("Explain code using AI (Ctrl+Alt+E)")
            layout.addWidget(self.explain_ai_btn)

        # Describe (F4) - table and schema
        if hasattr(manager, 'ws_describe_object_action'):
            self.describe_obj_btn = ToolbarActionButton(icon=manager.ws_describe_object_action.icon())
            self.describe_obj_btn.setDefaultAction(manager.ws_describe_object_action)
            self.describe_obj_btn.setIconSize(QSize(16, 16))
            self.describe_obj_btn.setMinimumWidth(32)
            self.describe_obj_btn.setToolTip("Describe (F4)")
            layout.addWidget(self.describe_obj_btn)

        # Quick Describe (Ctrl+D)
        if hasattr(manager, 'ws_quick_describe_action'):
            self.quick_describe_btn = ToolbarActionButton(icon=manager.ws_quick_describe_action.icon())
            self.quick_describe_btn.setDefaultAction(manager.ws_quick_describe_action)
            self.quick_describe_btn.setIconSize(QSize(16, 16))
            self.quick_describe_btn.setMinimumWidth(32)
            self.quick_describe_btn.setToolTip("Quick Describe (Ctrl+D)")
            layout.addWidget(self.quick_describe_btn)

        # Describe (parse) select query (Shift+F4)
        if hasattr(manager, 'ws_describe_action'):
            self.describe_btn = ToolbarActionButton(icon=manager.ws_describe_action.icon())
            self.describe_btn.setDefaultAction(manager.ws_describe_action)
            self.describe_btn.setIconSize(QSize(16, 16))
            self.describe_btn.setMinimumWidth(32)
            self.describe_btn.setToolTip("Describe (parse) select query (Shift+F4)")
            layout.addWidget(self.describe_btn)


        # Edit Menu
        self.edit_btn = ActionToolButton("", qta.icon("fa5s.edit", color="#555555"))
        self.edit_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.edit_btn.setFixedWidth(48)
        self.edit_btn.setToolTip("Edit Operations")
        
        edit_menu = QMenu(self)
        self._populate_edit_menu(edit_menu)
        self.edit_btn.setMenu(edit_menu)
        layout.addWidget(self.edit_btn)

        layout.addWidget(manager.create_vertical_separator())

        # Rows Limit
        self.rows_limit_combo = DropdownToolButton("", qta.icon("fa5s.list-ol"))
        self.rows_limit_combo.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.rows_limit_combo.setObjectName("rows_limit_combo")
        self.rows_limit_combo.setFixedWidth(48)
        self.rows_limit_combo.setToolTip("Row Limit")
        self.rows_limit_combo.addItems(["No Limit", "100", "500", "1000"])
        self.rows_limit_combo.itemTriggered.connect(
            lambda text: self.limit_changed.emit(text)
        )
        layout.addWidget(self.rows_limit_combo)

        layout.addWidget(manager.create_vertical_separator())
        layout.addStretch()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        super().paintEvent(event)

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
        
        self.setFixedHeight(26)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 6, 0)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        def _create_sep():
            sep = QFrame(self)
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setFrameShadow(QFrame.Shadow.Plain)
            sep.setFixedWidth(1)
            sep.setFixedHeight(14)
            sep.setStyleSheet("background-color: #CBD5E1; border: none; margin: 0 3px;")
            return sep

        # 1. Search Group at Far Left (button expands into search box)
        self.search_box = SearchBox()
        self.search_box.setFixedSize(105, 22)
        self.search_box.setStyleSheet("")
        self.search_box.setObjectName("table_search_box")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.hide()
        self.search_box.installEventFilter(manager)

        actions = self.search_box.actions()
        if actions:
            actions[0].triggered.connect(manager.toggle_table_search)

        self.table_search_btn = IconButton(
            qta.icon("fa5s.search", color="#475569", color_disabled="#CBD5E1"),
            "Search in Results",
        )
        self.table_search_btn.setObjectName("table_search_btn")
        self.table_search_btn.setFixedSize(22, 22)
        self.table_search_btn.setIconSize(QSize(12, 12))
        self.table_search_btn.clicked.connect(manager.toggle_table_search)

        self.search_debounce_timer = QTimer(self)
        self.search_debounce_timer.setInterval(300)
        self.search_debounce_timer.setSingleShot(True)
        self.search_debounce_timer.timeout.connect(self._trigger_filter)
        self.search_box.textChanged.connect(self._on_search_text_changed)

        layout.addWidget(self.search_box)
        layout.addWidget(self.table_search_btn)
        layout.addWidget(_create_sep())

        # 2. Row Actions Group
        self.add_row_btn = IconButton(
            qta.icon("ri.play-list-add-fill", color="#475569", color_disabled="#CBD5E1"),
            "Add new row",
        )
        self.add_row_btn.setObjectName("add_row_btn")
        self.add_row_btn.setFixedSize(22, 22)
        self.add_row_btn.setIconSize(QSize(12, 12))
        self.add_row_btn.clicked.connect(manager.add_empty_row)
        layout.addWidget(self.add_row_btn)

        self.save_row_btn = IconButton(
            qta.icon("fa5s.save", color="#475569", color_disabled="#CBD5E1"),
            "Save new row",
        )
        self.save_row_btn.setObjectName("save_row_btn")
        self.save_row_btn.setFixedSize(22, 22)
        self.save_row_btn.setIconSize(QSize(12, 12))
        self.save_row_btn.clicked.connect(manager.save_new_row)
        layout.addWidget(self.save_row_btn)

        self.delete_row_btn = IconButton(
            qta.icon("fa5s.trash-alt", color="#DC2626", color_disabled="#CBD5E1"),
            "Delete selected row(s)",
        )
        self.delete_row_btn.setObjectName("delete_row_btn")
        self.delete_row_btn.setFixedSize(22, 22)
        self.delete_row_btn.setIconSize(QSize(12, 12))
        self.delete_row_btn.clicked.connect(manager.delete_selected_row)
        layout.addWidget(self.delete_row_btn)

        # Separator between row actions and tools
        layout.addWidget(_create_sep())

        # 3. Export Group
        self.copy_btn = IconButton(
            qta.icon("fa5s.copy", color="#475569", color_disabled="#CBD5E1"),
            "Copy selected cells (Ctrl+C)",
        )
        self.copy_btn.setObjectName("copy_btn")
        self.copy_btn.setFixedSize(22, 22)
        self.copy_btn.setIconSize(QSize(12, 12))
        self.copy_btn.clicked.connect(manager.copy_current_result_table)
        layout.addWidget(self.copy_btn)

        self.download_btn = IconButton(
            qta.icon("fa5s.file-download", color="#475569", color_disabled="#CBD5E1"),
            "Download query result",
        )
        self.download_btn.setObjectName("download_btn")
        self.download_btn.setFixedSize(22, 22)
        self.download_btn.setIconSize(QSize(12, 12))
        self.download_btn.clicked.connect(lambda: manager.download_result(self.tab_content))
        layout.addWidget(self.download_btn)

        # Separator between tools and pagination
        layout.addWidget(_create_sep())

        # 3. Pagination and Limit Controls (icons only, zero clutter)
        self.rows_setting_btn = IconButton(
            qta.icon("fa5s.list-ul", color="#475569", color_disabled="#CBD5E1"),
            "Row limit & offset — Click to configure",
        )
        self.rows_setting_btn.setObjectName("rows_setting_btn")
        self.rows_setting_btn.setFixedSize(22, 22)
        self.rows_setting_btn.setIconSize(QSize(12, 12))
        self.rows_setting_btn.clicked.connect(lambda: manager.open_limit_offset_dialog(self.tab_content))
        layout.addWidget(self.rows_setting_btn)

        self.prev_btn = IconButton(
            qta.icon("fa5s.chevron-left", color="#475569", color_disabled="#CBD5E1"),
            "Previous page (Already at page 1)",
        )
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setObjectName("prev_btn")
        self.prev_btn.setFixedSize(22, 22)
        self.prev_btn.setIconSize(QSize(11, 11))
        self.prev_btn.clicked.connect(self._go_prev)
        layout.addWidget(self.prev_btn)

        self.next_btn = IconButton(
            qta.icon("fa5s.chevron-right", color="#475569", color_disabled="#CBD5E1"),
            "Next page",
        )
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setObjectName("next_btn")
        self.next_btn.setFixedSize(22, 22)
        self.next_btn.setIconSize(QSize(11, 11))
        self.next_btn.clicked.connect(self._go_next)
        layout.addWidget(self.next_btn)

        # Clear inline styles so style.qss controls all buttons uniformly at exactly 22x22
        for btn in (
            self.add_row_btn,
            self.save_row_btn,
            self.delete_row_btn,
            self.copy_btn,
            self.download_btn,
            self.table_search_btn,
            self.rows_setting_btn,
            self.prev_btn,
            self.next_btn,
        ):
            btn.setStyleSheet("")
            btn.setFixedSize(22, 22)

        # Compatibility hidden widgets (kept so existing findChild calls work without errors)
        self.rows_info_label = QLabel("Showing Rows", self)
        self.rows_info_label.setObjectName("rows_info_label")
        self.rows_info_label.hide()

        self.page_label = QLabel("Page 1", self)
        self.page_label.setObjectName("page_label")
        self.page_label.hide()

        self.nav_container = QWidget(self)
        self.nav_container.setObjectName("navContainer")
        self.nav_container.hide()

        self.update_page_ui(self.tab_content)
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
        current_page = getattr(tab, 'current_page', 1)
        self.page_label.setText(f"Page {current_page}")
        self.prev_btn.setEnabled(current_page > 1)
        self.prev_btn.setToolTip(f"Previous page (Page {current_page - 1})" if current_page > 1 else "Previous page")

        limit = getattr(tab, "current_limit", 0)
        offset = getattr(tab, "current_offset", 0)
        has_more_pages = getattr(tab, "has_more_pages", False)
        
        if limit == 0:
            self.next_btn.setEnabled(False)
            self.next_btn.setToolTip("Next page (No limit set)")
            self.rows_setting_btn.setToolTip("Row Limit: No Limit (click to configure)")
        else:
            self.next_btn.setEnabled(has_more_pages)
            self.next_btn.setToolTip(f"Next page (Page {current_page + 1})" if has_more_pages else "Next page (End of results)")
            self.rows_setting_btn.setToolTip(f"Row Limit: {limit} | Offset: {offset} (click to configure)")

        if limit and limit > 0:
            self.rows_info_label.setText(f"Limit: {limit} | Offset: {offset}")
        else:
            self.rows_info_label.setText("No Limit")

    def moveEvent(self, event):
        super().moveEvent(event)
        if self.y() != 0:
            self.move(self.x(), 0)


class ProcessFilterBar(QWidget):
    """
    Toolbar for filtering processes in the Processes View.
    """
    def __init__(self, manager, tab_content, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.tab_content = tab_content
        self.setObjectName("processFilterBar")
        self.setFixedHeight(34)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

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
            btn.setFixedHeight(26)
            btn.setMinimumWidth(50)
            btn.setMaximumWidth(100)
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
        self.search_edit.setFixedHeight(26)
        self.search_edit.setMinimumWidth(70)
        self.search_edit.setMaximumWidth(130)
        self.search_edit.textChanged.connect(lambda text: self.manager._filter_processes_table(self.tab_content, text))
        layout.addWidget(self.search_edit)
        
        # Action buttons
        self.view_log_btn = CompactButton(qta.icon("fa5s.file-alt", color="#374151"), "View Log")
        self.view_log_btn.setObjectName("process_view_log_btn")
        self.view_log_btn.setFixedHeight(26)
        self.view_log_btn.clicked.connect(lambda: self.manager._handle_view_log(self.tab_content))
        layout.addWidget(self.view_log_btn)

        self.refresh_now_btn = CompactButton("Refresh")
        self.refresh_now_btn.setObjectName("process_refresh_now_btn")
        self.refresh_now_btn.setFixedHeight(26)
        self.refresh_now_btn.clicked.connect(self.manager.refresh_processes_view)
        layout.addWidget(self.refresh_now_btn)

        self.hide() # Hidden by default
