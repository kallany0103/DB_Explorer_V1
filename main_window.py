# main_window.py
#from PyQt6.QtWidgets import QMainWindow, QTabWidget, QSplitter, QStatusBar, QPushButton, QMessageBox, QLabel
#from PyQt6.QtCore import Qt, QSize, QThreadPool, QTimer
from PySide6.QtWidgets import QMainWindow, QTabWidget, QSplitter, QStatusBar, QPushButton, QMessageBox, QLabel
from PySide6.QtCore import Qt, QSize, QThreadPool, QTimer
from PySide6.QtGui import QIcon
from widgets import NotificationManager, ConnectionManager, WorksheetManager, ResultsManager
from widgets.app_shell import (
    build_main_window_actions,
    build_main_window_menu,
    apply_main_window_styles,
    open_find_dialog,
    on_find_next,
    on_find_prev,
    on_replace,
    on_replace_all,
    open_sql_file,
    save_sql_file,
    save_sql_file_as,
    close_current_tab,
    close_all_tabs,
    close_tab,
    restore_tool,
    toggle_maximize,
    open_help_url,
    update_thread_pool_status,
    restore_main_window_session,
    save_main_window_session,
)


class MainWindow(QMainWindow):
    QUERY_TIMEOUT = 360000
    def __init__(self):
        super().__init__()
        self.SESSION_FILE = "session_state.json"

        self.setWindowTitle("Universal SQL Client")
        self.setWindowIcon(QIcon("assets/sql_icon.svg"))
        self.setGeometry(100, 100, 1200, 800)

        self.thread_pool = QThreadPool.globalInstance()
        self._saved_tree_paths = []

        # 1. Initialize Status Bar (needed by managers)
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_message_label = QLabel("Ready")
        self.status.addWidget(self.status_message_label)

        # 2. Initialize Tab Widget (needed by managers)
        self.tab_widget = QTabWidget()
        self.tab_widget.setMinimumWidth(200)
        self.tab_widget.setIconSize(QSize(16, 16))
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        # 3. Create Actions & Menus (needed by managers)
        self._create_actions()
        self._create_menu()

        # 4. Initialize Notification Manager (needed by ConnectionManager)
        self.notification_manager = NotificationManager(self)

        # 5. --- Initialize Managers ---
        self.connection_manager = ConnectionManager(self)
        self.results_manager = ResultsManager(self)
        self.worksheet_manager = WorksheetManager(self)

        # --- Compatibility Aliases ---
        self.tree = self.connection_manager.tree
        self.model = self.connection_manager.model
        self.proxy_model = self.connection_manager.proxy_model
        self.schema_tree = self.connection_manager.schema_tree
        self.schema_model = self.connection_manager.schema_model

        # --- Layout Setup ---
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(2)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setCentralWidget(self.main_splitter)

        # Add widgets to splitter
        # The ConnectionManager IS the left panel widget
        self.main_splitter.addWidget(self.connection_manager)
        self.main_splitter.addWidget(self.tab_widget)

        # 6. Additional UI for Tab Widget
        add_tab_btn = QPushButton("New")
        add_tab_btn.setObjectName("add_tab_btn")
        add_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_tab_btn.setToolTip("New Worksheet (Alt+Ctrl+S)")
        add_tab_btn.clicked.connect(self.add_tab)
        
        # Tab-integrated neutral style
        add_tab_btn.setStyleSheet("""
            QPushButton#add_tab_btn { 
                padding: 5px 12px;
                border: 1px solid #B8BEC6;
                background-color: #ECEFF3;
                border-radius: 3px;
                color: #1f2937;
                font-weight: 600;
                font-size: 9pt;
                text-align: center;
            }
            QPushButton#add_tab_btn:hover {
                background-color: #DDE2E8;
                border: 1px solid #9FA6AF;
            }
            QPushButton#add_tab_btn:pressed {
                background-color: #CED5DE;
            }
        """)
        self.tab_widget.setCornerWidget(add_tab_btn)

        self.thread_monitor_timer = QTimer()
        self.thread_monitor_timer.timeout.connect(self.update_thread_pool_status)
        self.thread_monitor_timer.start(1000)

        self._apply_styles()
        self.restore_session_state()
        self.main_splitter.setSizes([280, 920])
        self.raise_()
        self.activateWindow()

    # =========================================================================
    # --- CORE WORKSHEET TAB ACTIONS ---
    # =========================================================================

    def add_tab(self):
        return self.worksheet_manager.add_tab()

    def renumber_tabs(self):
        self.worksheet_manager.renumber_tabs()


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


    def refresh_object_explorer(self):
        self.connection_manager.refresh_object_explorer()

    def execute_query(self, *args, **kwargs):
        return self.worksheet_manager.execute_query(*args, **kwargs)

    def execute_query_in_new_output_tab(self):
        return self.worksheet_manager.execute_query(output_mode="new")


    def refresh_all_comboboxes(self):
        self.worksheet_manager.refresh_all_comboboxes()


    def load_joined_connections(self, combo_box):
        return self.worksheet_manager.load_joined_connections(combo_box)

    # =========================================================================
    # --- APP SHELL BUILDERS (ACTIONS / MENUS / FILE) ---
    # =========================================================================

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

    # =========================================================================
    # --- FIND / REPLACE MENU ACTIONS ---
    # =========================================================================

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

    # =========================================================================
    # --- EDITOR / QUERY COMMANDS ---
    # =========================================================================

    def format_sql_text(self):
        self.worksheet_manager.format_sql_text()

    def clear_query_text(self):
        self.worksheet_manager.clear_query_text()

    def show_about_dialog(self):
        QMessageBox.about(self, "About SQL Client", "<b>SQL Client Application</b><p>Version 1.0.0</p><p>This is a versatile SQL client designed to connect to and manage multiple database systems including PostgreSQL and SQLite.</p><p><b>Features:</b></p><ul><li>Object Explorer for database schemas</li><li>Multi-tab query editor with syntax highlighting</li><li>Query history per connection</li><li>Asynchronous query execution to keep the UI responsive</li></ul><p>Developed to provide a simple and effective tool for database management.</p>")

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
        close_current_tab(self)

    def close_all_tabs(self):
        close_all_tabs(self)

    def close_tab(self, index):
        close_tab(self, index)

    # =========================================================================
    # --- WINDOW / HELP / STYLE / SESSION ---
    # =========================================================================

    def restore_tool(self):
        restore_tool(self)




    def toggle_maximize(self):
        toggle_maximize(self)

    def open_help_url(self, url_string):
        open_help_url(self, url_string)
            
            
    def update_thread_pool_status(self):
        update_thread_pool_status(self)
   

    def _apply_styles(self):
        apply_main_window_styles(self)
        

    def closeEvent(self, event):
        """Confirm exit and save session state."""
        active_queries = len(self.worksheet_manager.running_queries)
        
        if active_queries > 0:
            msg = f"There are {active_queries} active queries running.\n\nAre you sure you want to quit and cancel them?"
        else:
            msg = "Are you sure you want to exit the application?"

        reply = QMessageBox.question(
            self, 
            "Confirm Exit", 
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            save_main_window_session(self, self.SESSION_FILE)
            
            # Cancel all running queries before exit
            for tab, runner in list(self.worksheet_manager.running_queries.items()):
                try:
                    runner.cancel()
                except Exception:
                    pass
                    
            event.accept()
        else:
            event.ignore()

    def restore_session_state(self):
        """Restore tabs and connections from saved session."""
        restore_main_window_session(self, self.SESSION_FILE)

    # =========================================================================
    # --- SCHEMA / CONNECTION MANAGER DELEGATIONS ---
    # =========================================================================

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

    # =========================================================================
    # --- RESULTS MANAGER DELEGATIONS ---
    # =========================================================================

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
        self.results_manager.handle_process_finished(process_id, message, time_taken, row_count)

    def handle_process_error(self, process_id, error_message):
        self.results_manager.handle_process_error(process_id, error_message)

    def refresh_processes_view(self):
        self.results_manager.refresh_processes_view()

    def update_page_label(self, target_tab, row_count):
        self.results_manager.update_page_label(target_tab, row_count)

    def stop_spinner(self, target_tab, success=True, target_index=0):
        self.results_manager.stop_spinner(target_tab, success=success, target_index=target_index)

    # =========================================================================
    # --- WORKSHEET MANAGER DELEGATIONS ---
    # =========================================================================

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
