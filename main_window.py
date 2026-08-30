# main_window.py
from PySide6.QtWidgets import QMainWindow, QTabWidget, QSplitter, QStatusBar, QMessageBox, QLabel, QMenu, QProgressDialog
from PySide6.QtCore import Qt, QSize, QThreadPool, QTimer, QPoint, QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QAction
import qtawesome as qta
from ui.components import SecondaryButton
from ui.title_bar import TitleBarWidget
from ui.resize_filter import ResizeFilter
from widgets.erd.widget import ERDWidget
from widgets import ConnectionManager, WorksheetManager, ResultsManager
from widgets.dashboard import DashboardWidget
from widgets.inspector.properties_view import PropertiesWorkbench
from widgets.inspector.statistics_view import StatisticsWorkbench
from widgets.usql_tool.terminal_widget import USQLToolWidget
from dialogs import PreferencesDialog
from widgets.login_dialog import LoginDialog
from ui.theme import setup_theme
import db

from widgets.app_shell import (
    build_main_window_actions,
    build_main_window_menu,
    save_main_window_session,
    restore_main_window_session,
    open_sql_file,
    save_sql_file,
    save_sql_file_as,
    open_find_dialog,
    on_find_next,
    on_find_prev,
    on_replace,
    on_replace_all,
    close_current_tab as close_current_tab_action,
    close_all_tabs as close_all_tabs_action,
    close_tab as close_tab_action,
    reset_layout as reset_layout_action,
    toggle_maximize as toggle_maximize_action,
    open_help_url as open_help_url_action,
    update_thread_pool_status as update_thread_pool_status_action,
    reset_to_dashboard as reset_to_dashboard_action,
    export_connections,
    import_connections,
)
from ui.account_menu import AccountMenu
from auth.session import AuthSession
from workers.google_login_worker import GoogleSignInWorker

class MainWindow(QMainWindow):
    QUERY_TIMEOUT = 360000
    def __init__(self):
        super().__init__()
        self.SESSION_FILE = "session_state.json"

        self.setWindowTitle("Universal SQL Client")
        self.setWindowIcon(QIcon("assets/sql_icon.png"))
        # VS Code standard: minimum 400×270; default first-launch 1200×800 centered.
        self.setMinimumSize(400, 270)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)

        self.thread_pool = QThreadPool.globalInstance()
        self._saved_tree_paths = []
        self.pg_bin_path = ""
        self.use_wsl = False

        self.auth_session = AuthSession(self)
        self.auth_session.state_changed.connect(self._on_auth_state_changed)
        self._google_worker = None
        self._google_progress = None
        self.auth_session.refresh_avatar()

        # 1. Initialize Status Bar (needed by managers)
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_message_label = QLabel("Ready")
        self.thread_pool_status_label = QLabel(
            f"ThreadPool: 0 active of {self.thread_pool.maxThreadCount()}"
        )
        self.status.addPermanentWidget(self.thread_pool_status_label)

        # 2. Initialize Tab Widget (needed by managers)
        self.tab_widget = QTabWidget()
        self.tab_widget.setMinimumWidth(200)
        self.tab_widget.setIconSize(QSize(16, 16))
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        self.tab_widget.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # 3. Create Actions & Menus (needed by managers)
        self._create_actions()
        self._create_menu()

        # 3a. Custom title bar — embeds the menu bar (replaces OS title bar)
        self._title_bar = TitleBarWidget(self)
        self._title_bar.embed_menu_bar(self.menuBar())
        self.setMenuWidget(self._title_bar)
        self._title_bar.set_user_state(self.auth_session)

        # 4 Initialize Managers

        self.connection_manager = ConnectionManager(self)
        self.results_manager = ResultsManager(self)
        self.worksheet_manager = WorksheetManager(self)
        self.dashboard_widget = None

        # Wire tab bar right-click context menu (WorksheetManager must exist first)
        self.tab_widget.tabBar().customContextMenuRequested.connect(
            self.worksheet_manager.show_tab_context_menu
        )

        # Keep the splash screen responsive while the main window is being built
        QApplication.processEvents()

        # Compatibility Aliases
        self.tree = self.connection_manager.tree
        self.model = self.connection_manager.model
        self.proxy_model = self.connection_manager.proxy_model
        self.schema_tree = self.connection_manager.schema_tree
        self.schema_model = self.connection_manager.schema_model

        # Layout Setup
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(2)
        self.main_splitter.setChildrenCollapsible(True)
        self.main_splitter.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setCentralWidget(self.main_splitter)

        # Add widgets to splitter
        # The ConnectionManager IS the left panel widget
        self.main_splitter.addWidget(self.connection_manager)
        self.main_splitter.addWidget(self.tab_widget)

        # Keep the splash screen responsive while the main window is being built
        QApplication.processEvents()

        # 6. Additional UI for Tab Widget
        add_tab_btn = SecondaryButton("New ")
        add_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_tab_btn.setIcon(qta.icon('fa5s.caret-down', color='#1f2937'))
        add_tab_btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        add_tab_btn.setToolTip("New Tab Options")

        # Create Dropdown Menu
        new_tab_menu = QMenu(self)
        new_tab_menu.setObjectName("new_tab_menu")
        new_tab_menu.setCursor(Qt.CursorShape.PointingHandCursor)

        action_new_worksheet = QAction(qta.icon('mdi.database-edit', scale_factor=1.3), "New Worksheet", self)
        action_new_worksheet.setShortcut("Ctrl+N")
        action_new_worksheet.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        action_new_worksheet.triggered.connect(self.add_tab)

        action_new_erd = QAction(qta.icon('fa6s.sitemap'), "New ERD", self)
        action_new_erd.setShortcut("Ctrl+Shift+E")
        action_new_erd.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        action_new_erd.triggered.connect(self.add_erd_tab)

        new_tab_menu.addAction(action_new_worksheet)
        new_tab_menu.addAction(action_new_erd)

        # Explicitly add actions to the window so their shortcuts trigger regardless of whether the dropdown is open
        self.addAction(action_new_worksheet)
        self.addAction(action_new_erd)

        # Style for the dropdown menu
        new_tab_menu.setStyleSheet("""
            QMenu#new_tab_menu {
                background-color: #FFFFFF;
                border: 1px solid #B8BEC6;
                border-radius: 4px;
                padding: 4px 0px 4px 4px;
            }
            QMenu#new_tab_menu::item {
                padding: 6px 24px 6px 4px;
                color: #1f2937;
                font-size: 9pt;
            }
            QMenu#new_tab_menu::item:selected {
                background-color: #E8E8E8;
                color: #000000;
            }
        """)

        def show_new_tab_menu():
            menu_width = new_tab_menu.sizeHint().width()
            x_pos = add_tab_btn.width() - menu_width
            new_tab_menu.exec(add_tab_btn.mapToGlobal(QPoint(x_pos, add_tab_btn.height() + 2)))

        add_tab_btn.clicked.connect(show_new_tab_menu)
        self.tab_widget.setCornerWidget(add_tab_btn, Qt.Corner.TopRightCorner)

        self.thread_monitor_timer = QTimer()
        self.thread_monitor_timer.timeout.connect(self.update_thread_pool_status)
        self.thread_monitor_timer.start(1000)

        self.restore_session_state()

        screen = QApplication.primaryScreen().availableGeometry()
        if not self.isMaximized() and not self.isFullScreen():
            if self.width() >= screen.width() - 40 and self.height() >= screen.height() - 40:
                default_w, default_h = 1200, 800
                x = screen.x() + (screen.width() - default_w) // 2
                y = screen.y() + (screen.height() - default_h) // 2
                self.setGeometry(x, y, default_w, default_h)
            elif self.width() > screen.width() or self.height() > screen.height():
                self.resize(
                    min(self.width(), screen.width()),
                    min(self.height(), screen.height()),
                )

        if hasattr(self, "_title_bar"):
            self._title_bar.update_maximize_button()
        self._is_maximized: bool = False

        self._resize_filter = ResizeFilter(self)
        QApplication.instance().installEventFilter(self._resize_filter)

        QApplication.processEvents()

        self.main_splitter.setSizes([280, 920])
        
        # Connect tree selections for Inspector workbenches
        self.schema_tree.selectionModel().currentChanged.connect(self._on_schema_selection_changed)
        self.schema_tree.clicked.connect(lambda idx: self._on_schema_selection_changed(idx, None))
        
        self.tree.selectionModel().currentChanged.connect(self._on_connection_selection_changed)
        self.tree.clicked.connect(lambda idx: self._on_connection_selection_changed(idx, None))
        
        self.raise_()
        self.activateWindow()


    # CORE WORKSHEET TAB ACTIONS

    def add_tab(self):
        return self.worksheet_manager.add_tab()

    def add_erd_tab(self):
        erd_number = sum(
            1 for i in range(self.tab_widget.count())
            if getattr(self.tab_widget.widget(i), "is_empty_erd", False)
        ) + 1
        erd_widget = ERDWidget({})
        erd_widget.is_empty_erd = True
        index = self.tab_widget.addTab(erd_widget, f"ERD {erd_number}")
        self.tab_widget.setTabIcon(index, qta.icon('fa6s.sitemap'))
        self.tab_widget.setCurrentIndex(index)
        self.renumber_tabs()

    def add_dashboard_tab(self):
        # Prevent multiple dashboard tabs
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "Dashboard":
                widget = self.tab_widget.widget(i)
                self.dashboard_widget = widget
                self.tab_widget.setCurrentIndex(i)
                return

        dashboard_widget = DashboardWidget(self)
        self.dashboard_widget = dashboard_widget
        tab_title = "Dashboard"
        index = self.tab_widget.addTab(dashboard_widget, tab_title)
        self.tab_widget.setTabIcon(index, qta.icon('fa5s.th-large', color='#555555'))
        self.tab_widget.setCurrentIndex(index)
        self.renumber_tabs()

    def renumber_tabs(self):
        self.worksheet_manager.renumber_tabs()

    def _find_inspector_tab(self, workbench_cls):
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, workbench_cls):
                return i, widget
        return None, None

    def _populate_inspector_from_tree_selection(self, widget):
        schema_item, schema_data, schema_name = self.connection_manager._get_current_schema_item_data()
        if schema_data:
            prepared = self.connection_manager.prepare_inspector_item_data(schema_data, schema_name)
            widget.update_view(prepared, schema_name)
            return

        current_conn_idx = self.tree.selectionModel().currentIndex()
        if not current_conn_idx.isValid():
            return
        source_idx = self.proxy_model.mapToSource(current_conn_idx)
        item = self.model.itemFromIndex(source_idx)
        if item and self.connection_manager.get_item_depth(item) == 3:
            item_data = item.data(Qt.ItemDataRole.UserRole)
            if item_data:
                prepared = self.connection_manager.prepare_inspector_item_data(
                    item_data, item.text()
                )
                widget.update_view(prepared, item.text())

    def _ensure_properties_workbench(self):
        _, widget = self._find_inspector_tab(PropertiesWorkbench)
        if widget is not None:
            return widget
        widget = PropertiesWorkbench(self)
        index = self.tab_widget.addTab(widget, "Properties")
        self.tab_widget.setTabIcon(index, qta.icon('mdi.tune'))
        return widget

    def _ensure_statistics_workbench(self):
        _, widget = self._find_inspector_tab(StatisticsWorkbench)
        if widget is not None:
            return widget
        widget = StatisticsWorkbench(self)
        index = self.tab_widget.addTab(widget, "Statistics")
        self.tab_widget.setTabIcon(index, qta.icon('mdi.chart-bar'))
        return widget

    def show_properties_workbench(self, item_data, obj_name):
        if item_data is None:
            QMessageBox.warning(self, "Properties", "No object selected.")
            return
        prepared = self.connection_manager.prepare_inspector_item_data(item_data, obj_name)
        widget = self._ensure_properties_workbench()
        self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(widget))
        widget.update_view(prepared, obj_name)

    def show_statistics_workbench(self, item_data, obj_name):
        if item_data is None:
            QMessageBox.warning(self, "Statistics", "No object selected.")
            return
        prepared = self.connection_manager.prepare_inspector_item_data(item_data, obj_name)
        widget = self._ensure_statistics_workbench()
        self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(widget))
        widget.update_view(prepared, obj_name)

    def add_properties_tab(self):
        widget = self._ensure_properties_workbench()
        self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(widget))
        self._populate_inspector_from_tree_selection(widget)

    def add_statistics_tab(self):
        widget = self._ensure_statistics_workbench()
        self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(widget))
        self._populate_inspector_from_tree_selection(widget)

    def _on_schema_selection_changed(self, current, previous):
        if not current.isValid():
            return
            
        item, item_data, name = self.connection_manager._get_current_schema_item_data()
        if not item_data:
            return
            
        # Update all open inspector tabs
        prepared = self.connection_manager.prepare_inspector_item_data(item_data, name)
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, (PropertiesWorkbench, StatisticsWorkbench)):
                widget.update_view(prepared, name)

    def _on_connection_selection_changed(self, current, previous):
        if not current.isValid():
            return
            
        source_index = self.proxy_model.mapToSource(current)
        item = self.model.itemFromIndex(source_index)
        if not item:
            return

        depth = self.connection_manager.get_item_depth(item)
        item_data = item.data(Qt.ItemDataRole.UserRole)
        name = item.text()

        # Update the dashboard immediately when a database type, group, or connection is selected.
        if self.dashboard_widget is not None:
            self.dashboard_widget.request_stats_update(manual=True)

        if depth != 3 or not item_data:
            return
            
        prepared = self.connection_manager.prepare_inspector_item_data(item_data, name)

        # Update all open inspector tabs
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, (PropertiesWorkbench, StatisticsWorkbench)):
                widget.update_view(prepared, name)


    def load_data(self):
        self.connection_manager.load_data()

    def _create_table_from_menu(self):
        self.connection_manager._create_table_from_menu()

    def _create_view_from_menu(self):
        self.connection_manager._create_view_from_menu()

    def _query_tool_from_menu(self):
        self.connection_manager._query_tool_from_menu()

    def _delete_object_from_menu(self):
        self.connection_manager._delete_object_from_menu()


    def refresh_object_explorer(self, *args, **kwargs):
        self.connection_manager.refresh_object_explorer(*args, **kwargs)

    def execute_query(self, *args, **kwargs):
        return self.worksheet_manager.execute_query(*args, **kwargs)

    def execute_query_in_new_output_tab(self):
        return self.worksheet_manager.execute_query(output_mode="new")

    def commit_transaction(self):
        return self.worksheet_manager.commit_transaction()

    def rollback_transaction(self):
        return self.worksheet_manager.rollback_transaction()

    def toggle_autocommit(self, checked: bool):
        return self.worksheet_manager.toggle_autocommit(checked)

    def refresh_all_comboboxes(self):
        self.worksheet_manager.refresh_all_comboboxes()


    def load_joined_connections(self, combo_box):
        return self.worksheet_manager.load_joined_connections(combo_box)

    # APP SHELL BUILDERS (ACTIONS / MENUS / FILE)

    def _create_actions(self):
        build_main_window_actions(self)


    def _create_menu(self):
        build_main_window_menu(self)

    def open_sql_file(self):
        open_sql_file(self)

    def save_sql_file(self):
        save_sql_file(self)

    def save_sql_file_as(self):
        save_sql_file_as(self)
        
    def export_connections(self):
        export_connections(self)
        
    def import_connections(self):
        import_connections(self)

    #FIND / REPLACE MENU ACTIONS

    def open_find_dialog(self, replace=False):
        open_find_dialog(self, replace)

    def _on_find_next(self, text, case, whole):
        on_find_next(self, text, case, whole)

    def _on_find_prev(self, text, case, whole):
        on_find_prev(self, text, case, whole)

    def _on_replace(self, target, replacement, case, whole):
        on_replace(self, target, replacement, case, whole)

    def _on_replace_all(self, target, replacement, case, whole):
        on_replace_all(self, target, replacement, case, whole)

    # EDITOR / QUERY COMMANDS

    def format_sql_text(self):
        self.worksheet_manager.format_sql_text()

    def clear_query_text(self, *args, **kwargs):
        self.worksheet_manager.clear_query_text()

    def show_about_dialog(self):
        QMessageBox.about(self, "About SQL Client", "<b>SQL Client Application</b><p>Version 1.37</p><p>This is a versatile SQL client designed to connect to and manage multiple database systems including PostgreSQL and SQLite.</p><p><b>Features:</b></p><ul><li>Object Explorer for database schemas</li><li>Multi-tab query editor with syntax highlighting</li><li>Query history per connection</li><li>Asynchronous query execution to keep the UI responsive</li></ul><p>Developed to provide a simple and effective tool for database management.</p>")

    def _get_current_editor(self):
        return self.worksheet_manager._get_current_editor()

    def undo_text(self):
        self.worksheet_manager.undo_text()

    def redo_text(self):
        self.worksheet_manager.redo_text()

    def cut_text(self):
        self.worksheet_manager.cut_text()

    def copy_text(self):
        self.worksheet_manager.copy_text()

    def paste_text(self):
        self.worksheet_manager.paste_text()

    def delete_text(self):
        self.worksheet_manager.delete_text()

    def select_all_text(self):
        editor = self._get_current_editor()
        if editor:
            editor.selectAll()

    def goto_line(self):
        self.worksheet_manager.go_to_line()

    def comment_block(self):
        editor = self._get_current_editor()
        if editor:
            editor.toggle_comment()

    def uncomment_block(self):
        editor = self._get_current_editor()
        if editor:
            editor.toggle_comment()

    def upper_case_text(self):
        editor = self._get_current_editor()
        if editor:
            cursor = editor.textCursor()
            if cursor.hasSelection():
                text = cursor.selectedText()
                cursor.insertText(text.upper())

    def lower_case_text(self):
        editor = self._get_current_editor()
        if editor:
            cursor = editor.textCursor()
            if cursor.hasSelection():
                text = cursor.selectedText()
                cursor.insertText(text.lower())

    def initial_caps_text(self):
        editor = self._get_current_editor()
        if editor:
            cursor = editor.textCursor()
            if cursor.hasSelection():
                text = cursor.selectedText()
                cursor.insertText(text.title())

    def explain_query(self):
        self.worksheet_manager.explain_query()

    def explain_plan_query(self):
        self.worksheet_manager.explain_plan_query()

    def cancel_current_query(self):
        self.worksheet_manager.cancel_current_query()

    def close_current_tab(self):
        close_current_tab_action(self)

    def close_all_tabs(self):
        close_all_tabs_action(self)

    def close_tab(self, index):
        # Keep dashboard reference accurate when the dashboard tab is closed.
        widget = self.tab_widget.widget(index)
        if widget is not None and widget is self.dashboard_widget:
            self.dashboard_widget = None

        if isinstance(widget, USQLToolWidget):
            widget.close_process()
        close_tab_action(self, index)


    # WINDOW / HELP / STYLE / SESSION

    def reset_layout(self, *args, **kwargs):
        reset_layout_action(self)

    def reset_to_dashboard(self, *args, **kwargs):
        reset_to_dashboard_action(self)

    def toggle_left_panel(self):
        """Collapse or expand the left sidebar panel.

        When collapsed: all header items except the toggle button are hidden,
        the stretch spacer is removed so the button sits top-left in a 32 px
        strip.  Clicking it restores the full sidebar.
        """
        import qtawesome as qta
        from PySide6.QtWidgets import QSpacerItem
        cm = self.connection_manager
        is_collapsed = getattr(self, '_sidebar_collapsed', False)

        if not is_collapsed:
            # ── COLLAPSE ──────────────────────────────────────────────────
            self._last_left_panel_width = self.main_splitter.sizes()[0]

            # Hide tree content
            cm.vertical_splitter.hide()
            if hasattr(cm, 'empty_space'):
                cm.empty_space.show()

            # Hide header items (label, search, add-btn)
            if hasattr(cm, 'explorer_label'):
                cm.explorer_label.hide()
            if hasattr(cm, 'explorer_search_container'):
                cm.explorer_search_container.hide()
            if hasattr(cm, 'explorer_add_btn'):
                cm.explorer_add_btn.hide()

            # Remove the stretch spacer so the button sits at the top-left
            if hasattr(cm, 'explorer_header_layout'):
                layout = cm.explorer_header_layout
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item and isinstance(item.spacerItem(), QSpacerItem):
                        layout.takeAt(i)
                        break
                # Tight margins: just enough room for the button
                layout.setContentsMargins(2, 6, 2, 0)
                layout.setSpacing(0)

            # Force the widget to shrink to exactly the button's width
            cm.setMinimumWidth(28)
            cm.setMaximumWidth(28)
            total = sum(self.main_splitter.sizes())
            self.main_splitter.setSizes([28, total - 28])

            # Flip button icon → expand arrow
            if hasattr(cm, 'collapse_panel_btn'):
                from PySide6.QtCore import QSize
                cm.collapse_panel_btn.setFixedSize(24, 24)
                cm.collapse_panel_btn.setIcon(
                    qta.icon('mdi.chevron-double-right', color='#6b7280')
                )
                cm.collapse_panel_btn.setToolTip("Show Sidebar")

            self._sidebar_collapsed = True

        else:
            # ── EXPAND ────────────────────────────────────────────────────
            # Restore header layout: add stretch back before search/add-btn
            if hasattr(cm, 'explorer_header_layout'):
                layout = cm.explorer_header_layout
                layout.setContentsMargins(8, 2, 8, 6)
                layout.setSpacing(10)
                # Re-insert stretch before search_container (index 1)
                layout.insertStretch(1, 1)

            # Show tree content
            if hasattr(cm, 'empty_space'):
                cm.empty_space.hide()
            cm.vertical_splitter.show()

            # Show header items
            if hasattr(cm, 'explorer_label'):
                cm.explorer_label.show()
            if hasattr(cm, 'explorer_search_container'):
                cm.explorer_search_container.show()
            if hasattr(cm, 'explorer_add_btn'):
                cm.explorer_add_btn.show()

            # Restore previous width constraint
            cm.setMinimumWidth(0)
            cm.setMaximumWidth(16777215)
            
            # Restore previous width
            restore_w = getattr(self, '_last_left_panel_width', 280)
            total = sum(self.main_splitter.sizes())
            self.main_splitter.setSizes([restore_w, total - restore_w])

            # Flip button icon → collapse arrow
            if hasattr(cm, 'collapse_panel_btn'):
                from PySide6.QtCore import QSize
                cm.collapse_panel_btn.setFixedSize(24, 24)
                cm.collapse_panel_btn.setIcon(
                    qta.icon('mdi.chevron-double-left', color='#6b7280')
                )
                cm.collapse_panel_btn.setToolTip("Hide Sidebar")

            self._sidebar_collapsed = False

    def toggle_maximize(self):
        toggle_maximize_action(self)
        if hasattr(self, "_title_bar"):
            self._title_bar.update_maximize_button()

    def changeEvent(self, event: QEvent) -> None:
        """Keep the maximize button in sync when the OS changes window state."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            if hasattr(self, "_title_bar"):
                self._title_bar.update_maximize_button()


    def open_help_url(self, url_string):
        open_help_url_action(self, url_string)

    def update_thread_pool_status(self):
        update_thread_pool_status_action(self)
   
    def show_preferences(self):
        dialog = PreferencesDialog(self)
        if dialog.exec():
            settings = dialog.get_settings()
            self.pg_bin_path = settings.get("pg_bin_path", "")
            self.use_wsl = settings.get("use_wsl", False)
            
            new_theme = settings.get("theme", "Light")
            if getattr(self, "theme", "Light") != new_theme:
                self.theme = new_theme
                setup_theme(QApplication.instance(), new_theme)
                
            # Save session immediately to persist settings
            save_main_window_session(self, self.SESSION_FILE)

    def show_login(self):
        dialog = LoginDialog(self)
        dialog.exec()

    def show_login_menu(self, anchor):
        if self.isMinimized():
            return
        menu = AccountMenu(
            parent=self,
            signed_in=self.auth_session.is_signed_in,
            display_name=self.auth_session.display_name,
            email=(self.auth_session.user or {}).get("email", ""),
            on_google=self._sign_in_google,
            on_email=self.show_login,
            on_sign_out=self._sign_out,
        )
        menu.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        menu.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, True)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        menu.exec(self._menu_position_within_window(menu, anchor))

    def _menu_position_within_window(self, menu, anchor):
        """Place the account panel left of its anchor and inside the app window."""
        window_rect = self.geometry()
        menu_size = menu.sizeHint()
        anchor_bottom_right = anchor.mapToGlobal(
            QPoint(anchor.width(), anchor.height())
        )
        pos = QPoint(
            anchor_bottom_right.x() - menu_size.width(),
            anchor_bottom_right.y(),
        )
        pos.setX(
            max(window_rect.left(), min(pos.x(), window_rect.right() - menu_size.width() + 1))
        )
        pos.setY(
            max(window_rect.top(), min(pos.y(), window_rect.bottom() - menu_size.height() + 1))
        )
        return pos

    def _sign_in_google(self) -> None:
        if self._google_worker is not None and self._google_worker.isRunning():
            return
        self._google_worker = GoogleSignInWorker(self.auth_session, parent=self)
        self._google_worker.completed.connect(self._on_google_completed)
        self._google_worker.start()
        self._google_progress = QProgressDialog(
            "Waiting for browser...\nComplete Google sign-in to continue.",
            "Cancel",
            0,
            0,
            self,
        )
        self._google_progress.setWindowTitle("Google sign-in")
        self._google_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._google_progress.setMinimumDuration(0)
        self._google_progress.canceled.connect(self._google_worker.cancel)
        self._google_progress.show()

    def _on_google_completed(self, success: bool, message: str) -> None:
        if self._google_progress is not None:
            self._google_progress.close()
            self._google_progress = None
        if not success and message:
            QMessageBox.warning(self, "Google sign-in", message)

    def _sign_out(self) -> None:
        self.auth_session.sign_out()

    def _on_auth_state_changed(self, signed_in: bool) -> None:
        self._title_bar.set_user_state(self.auth_session)
   

    def closeEvent(self, event):
        """Confirm exit and save session state."""
        active_queries = len(self.worksheet_manager.running_queries)

        if active_queries > 0:
            msg = f"There are {active_queries} active queries running.\n\nAre you sure you want to quit and cancel them?"
        else:
            msg = "Are you sure you want to exit the application?"

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Confirm Exit")
        msg_box.setText(msg)
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        yes_btn = msg_box.addButton("Yes", QMessageBox.ButtonRole.YesRole)
        no_btn = msg_box.addButton("No", QMessageBox.ButtonRole.NoRole)
        msg_box.setDefaultButton(no_btn)

        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

        msg_box.exec()

        if msg_box.clickedButton() == yes_btn:
            save_main_window_session(self, self.SESSION_FILE)

            # Cancel all running queries before exit
            for tab, runner in list(self.worksheet_manager.running_queries.items()):
                try:
                    runner.cancel()
                except Exception:
                    pass

            # Close all PostgreSQL connection pools
            try:
                db.close_all_postgres_pools()
            except Exception as e:
                print(f"Error closing connection pools: {e}")

            event.accept()
        else:
            event.ignore()

    def restore_session_state(self):
        """Restore tabs and connections from saved session."""
        restore_main_window_session(self, self.SESSION_FILE)

    #SCHEMA / CONNECTION MANAGER DELEGATIONS

    def load_postgres_schema(self, conn_data):
        self.connection_manager.load_postgres_schema(conn_data)

    def load_sqlite_schema(self, conn_data):
        self.connection_manager.load_sqlite_schema(conn_data)

    def load_csv_schema(self, conn_data):
        self.connection_manager.load_csv_schema(conn_data)

    def load_servicenow_schema(self, conn_data):
        self.connection_manager.load_servicenow_schema(conn_data)

    def load_tables_on_expand(self, index):
        self.connection_manager.table_details_loader.load_tables_on_expand(index)

    def show_schema_context_menu(self, position):
        self.connection_manager.show_schema_context_menu(position)

    def show_table_properties(self, item_data, table_name):
        self.connection_manager.connection_actions.show_table_properties(item_data, table_name)

    def query_table_rows(self, item_data, table_name, limit=None, execute_now=True, order=None):
        self.connection_manager.connection_actions.query_table_rows(item_data, table_name, limit=limit, execute_now=execute_now, order=order)

    def count_table_rows(self, item_data, table_name):
        self.connection_manager.connection_actions.count_table_rows(item_data, table_name)

    def open_query_tool_for_table(self, item_data, display_name):
        self.connection_manager.connection_actions.open_query_tool_for_table(item_data, display_name)

    def script_table_as_create(self, item_data, table_name):
        self.connection_manager.script_generator.script_table_as_create(item_data, table_name)

    def script_table_as_insert(self, item_data, table_name):
        self.connection_manager.script_generator.script_table_as_insert(item_data, table_name)

    def script_table_as_update(self, item_data, table_name):
        self.connection_manager.script_generator.script_table_as_update(item_data, table_name)

    def script_table_as_delete(self, item_data, table_name):
        self.connection_manager.script_generator.script_table_as_delete(item_data, table_name)

    def script_table_as_select(self, item_data, table_name):
        self.connection_manager.script_generator.script_table_as_select(item_data, table_name)

    def delete_table(self, item_data, table_name):
        self.connection_manager.connection_actions.delete_table(item_data, table_name)

    def delete_sequence(self, item_data, seq_name):
        self.connection_manager.connection_actions.delete_sequence(item_data, seq_name)

    def script_sequence_as_create(self, item_data, seq_name):
        self.connection_manager.script_generator.script_sequence_as_create(item_data, seq_name)

    def script_function_as_create(self, item_data, func_name):
        self.connection_manager.script_generator.script_function_as_create(item_data, func_name)

    def delete_function(self, item_data, func_name):
        self.connection_manager.connection_actions.delete_function(item_data, func_name)

    def open_create_function_template(self, item_data):
        self.connection_manager.script_generator.open_create_function_template(item_data)

    def open_create_trigger_function_template(self, item_data):
        self.connection_manager.script_generator.open_create_trigger_function_template(item_data)

    def script_language_as_create(self, item_data, lan_name):
        self.connection_manager.script_generator.script_language_as_create(item_data, lan_name)

    def delete_language(self, item_data, lan_name):
        self.connection_manager.connection_actions.delete_language(item_data, lan_name)

    def drop_extension(self, item_data, ext_name, cascade=False):
        self.connection_manager.connection_actions.drop_extension(item_data, ext_name, cascade=cascade)

    def create_extension_dialog(self, item_data):
        self.connection_manager.connection_actions.create_extension_dialog(item_data)

    def create_fdw_template(self, item_data):
        self.connection_manager.connection_actions.create_fdw_template(item_data)

    def create_foreign_server_template(self, item_data):
        self.connection_manager.connection_actions.create_foreign_server_template(item_data)

    def create_user_mapping_template(self, item_data):
        self.connection_manager.connection_actions.create_user_mapping_template(item_data)

    def import_foreign_schema_dialog(self, item_data):
        self.connection_manager.connection_actions.import_foreign_schema_dialog(item_data)

    def drop_fdw(self, item_data):
        self.connection_manager.connection_actions.drop_fdw(item_data)

    def drop_foreign_server(self, item_data):
        self.connection_manager.connection_actions.drop_foreign_server(item_data)

    def drop_user_mapping(self, item_data):
        self.connection_manager.connection_actions.drop_user_mapping(item_data)

    def export_schema_table_rows(self, item_data, table_name):
        self.connection_manager.connection_actions.export_schema_table_rows(item_data, table_name)

    def open_create_table_template(self, item_data, table_name=None):
        self.connection_manager.connection_actions.open_create_table_template(item_data, table_name=table_name)

    def open_create_view_template(self, item_data):
        self.connection_manager.connection_actions.open_create_view_template(item_data)

    def show_error_popup(self, msg):
        self.connection_manager.show_error_popup(msg)

    def _execute_simple_sql(self, item_data, sql):
        self.connection_manager.connection_actions.execute_simple_sql(item_data, sql)

    def _open_script_in_editor(self, item_data, sql):
        self.connection_manager.script_generator.open_script_in_editor(item_data, sql)

    # RESULTS MANAGER DELEGATIONS

    def handle_query_result(self, target_tab, output_mode, output_tab_index, conn_data, query, results, columns, row_count, elapsed_time, is_select_query):
        self.worksheet_manager.handle_query_result(target_tab, output_mode, output_tab_index, conn_data, query, results, columns, row_count, elapsed_time, is_select_query)

    def show_results_context_menu(self, position):
        self.results_manager.show_results_context_menu(position)

    def export_result_rows(self, table_view):
        self.results_manager.export_result_rows(table_view)

    def _initialize_processes_model(self, tab_content):
        self.results_manager._initialize_processes_model(tab_content)

    def switch_to_processes_view(self):
        self.results_manager.switch_to_processes_view()

    def get_current_tab_processes_model(self):
        return self.results_manager.get_current_tab_processes_model()

    def handle_process_started(self, process_id, data):
        self.results_manager.handle_process_started(process_id, data)

    def handle_process_finished(self, process_id, message, time_taken, row_count):
        if hasattr(self, "_active_processes") and process_id in self._active_processes:
            del self._active_processes[process_id]
        self.results_manager.handle_process_finished(process_id, message, time_taken, row_count)

    def handle_process_error(self, process_id, error_message):
        if hasattr(self, "_active_processes") and process_id in self._active_processes:
            del self._active_processes[process_id]
        self.results_manager.handle_process_error(process_id, error_message)

    def handle_process_output(self, process_id, text):
        self.results_manager.handle_process_output(process_id, text)

    def refresh_processes_view(self):
        self.results_manager.refresh_processes_view()

    def update_page_label(self, target_tab, row_count):
        self.results_manager.update_page_label(target_tab, row_count)

    def stop_spinner(self, target_tab, success=True, target_index=0):
        self.results_manager.stop_spinner(target_tab, success=success, target_index=target_index)

    # WORKSHEET MANAGER DELEGATIONS

    def update_timer_label(self, label, tab):
        self.worksheet_manager.update_timer_label(label, tab)

    def handle_query_error(self, current_tab, output_tab_index, conn_data, query, row_count, elapsed_time, error_message):
        self.worksheet_manager.handle_query_error(current_tab, output_tab_index, conn_data, query, row_count, elapsed_time, error_message)

    def handle_query_timeout(self, tab, runnable):
        self.worksheet_manager.handle_query_timeout(tab, runnable)

    def show_info(self, text, parent=None):
        self.worksheet_manager.show_info(text, parent=parent)

    def save_query_to_history(self, conn_data, query, status, rows, duration):
        self.worksheet_manager.save_query_to_history(conn_data, query, status, rows, duration)
