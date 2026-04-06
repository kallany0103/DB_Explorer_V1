import qtawesome as qta

from PySide6.QtWidgets import (
    QWidget, QTextEdit,
    QFrame
)
from PySide6.QtCore import (
    QRect
)
from PySide6.QtGui import (
    QIcon
)

from widgets.worksheet.code_editor import CodeEditor
from widgets.worksheet.editor_actions import (
    format_sql_text as format_sql_text_action,
    clear_query_text as clear_query_text_action,
    undo_text as undo_text_action,
    redo_text as redo_text_action,
    cut_text as cut_text_action,
    copy_text as copy_text_action,
    paste_text as paste_text_action,
    delete_text as delete_text_action,
    go_to_line as go_to_line_action,
)
from widgets.worksheet.context_menu import show_editor_context_menu as show_editor_context_menu_action
from widgets.worksheet.query_executor import (
    start_query_worker,
    on_query_finished_signal,
    on_query_error_signal,
    explain_plan_query as explain_plan_query_action,
    explain_query as explain_query_action,
    execute_query as execute_query_action,
    update_timer_label as update_timer_label_action,
    show_error_popup as show_error_popup_action,
    handle_query_error as handle_query_error_action,
    handle_query_timeout as handle_query_timeout_action,
    cancel_current_query as cancel_current_query_action,
)
from widgets.worksheet.connections import (
    refresh_all_comboboxes as refresh_all_comboboxes_action,
    load_joined_connections as load_joined_connections_action,
)
from widgets.worksheet.tab_builder import add_tab as add_tab_action
from widgets.worksheet.history import (
    save_query_to_history as save_query_to_history_action,
    load_connection_history as load_connection_history_action,
    display_history_details as display_history_details_action,
    get_selected_history_item,
    copy_history_query as copy_history_query_action,
    copy_history_to_editor as copy_history_to_editor_action,
    remove_selected_history as remove_selected_history_action,
    remove_all_history_for_connection as remove_all_history_for_connection_action,
)
from widgets.worksheet.utils import renumber_tabs as renumber_tabs_action, handle_event_filter, show_info as show_info_action
from widgets.app_shell.file_ops import open_find_dialog as open_find_dialog_action

class WorksheetManager(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.tab_widget = main_window.tab_widget
        self.status = main_window.status
        self.thread_pool = main_window.thread_pool
        self.status_message_label = main_window.status_message_label
        self.cancel_action = main_window.cancel_action
        self.open_file_action = main_window.open_file_action
        self.save_as_action = main_window.save_as_action
        self.execute_action = main_window.execute_action
        self.execute_new_tab_action = main_window.execute_new_tab_action
        
        # Initialize helpers
        self.results_manager = main_window.results_manager
        self.tab_widget.currentChanged.connect(self._refresh_active_editor_layout)
        
        # State
        self.tab_timers = {}
        self.running_queries = {}
        self.QUERY_TIMEOUT = 300000
        self.worksheet_icon_key = "mdi.database-edit"
        self.worksheet_icon_fallback_key = "ri.layout-6-fill"
        

    def _get_worksheet_tab_icon(self):
        for icon_key in (self.worksheet_icon_key, self.worksheet_icon_fallback_key):
            try:
                return qta.icon(icon_key, scale_factor=1.15)
            except Exception:
                continue
        return QIcon()

    def _next_worksheet_tab_number(self):
        worksheet_count = 0
        for i in range(self.tab_widget.count()):
            tab_text = self.tab_widget.tabText(i)
            if tab_text.startswith("Worksheet ") or tab_text == "New Tab":
                worksheet_count += 1
        return worksheet_count + 1

    def _start_query_worker(self, current_tab, conn_data, query, output_mode="current", output_tab_index=None):
        return start_query_worker(self, current_tab, conn_data, query, output_mode, output_tab_index)

    def _on_query_finished_signal(self, conn_data, query, results, columns, column_specs, row_count, elapsed_time, is_select_query):
        on_query_finished_signal(self, conn_data, query, results, columns, column_specs, row_count, elapsed_time, is_select_query)

    def _on_query_error_signal(self, conn_data, query, row_count, elapsed_time, error_message):
        on_query_error_signal(self, conn_data, query, row_count, elapsed_time, error_message)

    def _get_current_editor(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
            return None
        return current_tab.findChild(CodeEditor, "query_editor")

# {mitayan}
    def _refresh_editor_layout_for_tab(self, tab):
        if not tab:
            return
        editor = tab.findChild(CodeEditor, "query_editor")
        if not editor:
            return
        editor.updateLineNumberAreaWidth(0)
        cr = editor.contentsRect()
        editor.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), editor.lineNumberAreaWidth(), cr.height()))
        editor.lineNumberArea.update()
        editor.viewport().update()

# {mitayan}
    def _refresh_active_editor_layout(self, _index):
        self._refresh_editor_layout_for_tab(self.tab_widget.currentWidget())

# {mitayan}
    def create_vertical_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #D3D3D3;")
        return line

    def format_sql_text(self):
        format_sql_text_action(self)


    def clear_query_text(self):
        clear_query_text_action(self)


    def undo_text(self):
        undo_text_action(self)

    def redo_text(self):
        redo_text_action(self)

    def cut_text(self):
        cut_text_action(self)

    def copy_text(self):
        copy_text_action(self)

    def paste_text(self):
        paste_text_action(self)

    def delete_text(self):
        delete_text_action(self)

    def go_to_line(self):
        go_to_line_action(self)



    def close_tab(self, index):
        if index < 0:
            index = self.tab_widget.currentIndex()
        if index >= 0 and self.tab_widget.count() > 0:
            widget = self.tab_widget.widget(index)
            if widget:
                if widget in self.running_queries:
                    self.running_queries[widget].cancel()
                    del self.running_queries[widget]
                    if not self.running_queries:
                        self.cancel_action.setEnabled(False)

                if widget in self.tab_timers:
                    self.tab_timers[widget]["timer"].stop()
                    self.tab_timers[widget]["timeout_timer"].stop()
                    del self.tab_timers[widget]

                self.results_manager.cleanup_tab_resources(widget)
                self.tab_widget.removeTab(index)
                widget.deleteLater()
            
            if self.tab_widget.count() == 0:
                self.add_tab()
            
            self.renumber_tabs()


    def add_tab(self):
        return add_tab_action(self)

    def open_find_dialog(self, replace=False):
        open_find_dialog_action(self, replace)


    def show_editor_context_menu(self, pos, editor):
        show_editor_context_menu_action(self, pos, editor)




    def explain_plan_query(self):
        explain_plan_query_action(self)
# {siam}


    def explain_query(self):
        explain_query_action(self)

    def execute_query(self, conn_data=None, query=None, output_mode="current", preserve_pagination=False):
        execute_query_action(self, conn_data, query, output_mode, preserve_pagination)

    def update_timer_label(self, label, tab):
        update_timer_label_action(self, label, tab)




    def show_error_popup(self, error_text, parent=None):
        show_error_popup_action(error_text, parent)

    def handle_query_error(self, current_tab, output_tab_index, conn_data, query, row_count, elapsed_time, error_message):
        handle_query_error_action(self, current_tab, output_tab_index, conn_data, query, row_count, elapsed_time, error_message)



    def handle_query_timeout(self, tab, runnable):
        handle_query_timeout_action(self, tab, runnable)

    def cancel_current_query(self):
        cancel_current_query_action(self)


    def save_query_to_history(self, conn_data, query, status, rows, duration):
        save_query_to_history_action(self, conn_data, query, status, rows, duration)

    def load_connection_history(self, target_tab):
        load_connection_history_action(self, target_tab)

    def display_history_details(self, index, target_tab):
        display_history_details_action(self, index, target_tab)

    def _get_selected_history_item(self, target_tab):
        return get_selected_history_item(self, target_tab)

    def copy_history_query(self, target_tab):
        copy_history_query_action(self, target_tab)

    def copy_history_to_editor(self, target_tab):
        copy_history_to_editor_action(self, target_tab)

    def remove_selected_history(self, target_tab):
        remove_selected_history_action(self, target_tab)

    def remove_all_history_for_connection(self, target_tab):
        remove_all_history_for_connection_action(self, target_tab)

    # --- Delegated Result Methods ---

    def handle_query_result(self, target_tab, output_mode, output_tab_index, conn_data, query, results, columns, column_specs, row_count, elapsed_time, is_select_query):
        if target_tab in self.tab_timers:
            self.tab_timers[target_tab]["timer"].stop()
            self.tab_timers[target_tab]["timeout_timer"].stop()
            del self.tab_timers[target_tab]

        try:
            self.results_manager.handle_query_result(
                target_tab,
                conn_data,
                query,
                results,
                columns,
                column_specs,
                row_count,
                elapsed_time,
                is_select_query,
                output_mode=output_mode,
                output_tab_index=output_tab_index,
            )
        except Exception as e:
            message_view = target_tab.findChild(QTextEdit, "message_view")
            if message_view:
                message_view.append(f"Error rendering query result:\n\n{str(e)}")
            self.results_manager.stop_spinner(target_tab, success=False)
            self.status_message_label.setText("Error occurred")
        self._refresh_editor_layout_for_tab(target_tab)

    def execute_query_in_new_output_tab(self):
        self.execute_query(output_mode="new")

    def renumber_tabs(self):
        renumber_tabs_action(self)

    def eventFilter(self, obj, event):
        if handle_event_filter(obj, event):
            return True
        return super().eventFilter(obj, event)

    def refresh_all_comboboxes(self):
        refresh_all_comboboxes_action(self)

    def show_info(self, text, parent=None):
        show_info_action(self, text, parent)

    def load_joined_connections(self, combo_box):
        load_joined_connections_action(self, combo_box)
