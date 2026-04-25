import os
import uuid
import datetime
import re
import copy
from numbers import Number

from PySide6.QtWidgets import (
    QTableView, QMessageBox, QMenu, QComboBox,
    QDialog, QToolButton, QStackedWidget,
    QWidget, QLabel, QPushButton, QTextEdit,
    QFormLayout, QSpinBox, QVBoxLayout, QHBoxLayout
)
from PySide6.QtCore import (
    Qt, QObject, QEvent
)
from PySide6.QtGui import (
    QAction
)

from db.query_context import resolve_writable_table_context
import widgets.results_view.clipboard as clipboard
import widgets.results_view.output_tabs as output_tabs
import widgets.results_view.processes as processes
import widgets.results_view.query_handler as query_handler
import widgets.results_view.row_crud as row_crud
import widgets.results_view.ui as ui
from widgets.results_view.perf_metrics import perf_snapshot
from dialogs import ExportDialog
from workers import RunnableExportFromModel, ProcessSignals
from workers.signals import emit_process_started

class ResultsManager(QObject):
    PROCESS_STATUS_META = {
        "RUNNING": {"label": "Running", "color": "#FFF4CC", "priority": 1},
        "SUCCESSFUL": {"label": "Successful", "color": "#E8F5E9", "priority": 2},
        "WARNING": {"label": "Warning", "color": "#FFF3E0", "priority": 3},
        "ERROR": {"label": "Error", "color": "#FDECEC", "priority": 4},
    }

    DEFAULT_PROCESS_STATUS_META = {
        "label": "Unknown",
        "color": "#8f959e",
        "priority": 99,
    }

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        # Proxies to main window attributes
        self.tab_widget = main_window.tab_widget
        self.status = main_window.status
        self.thread_pool = main_window.thread_pool
        self.status_message_label = main_window.status_message_label
        self.cancel_action = main_window.cancel_action
        
        # Internal state
        self.tab_timers = {}
        self.running_queries = {}
        self.QUERY_TIMEOUT = 300000  # Default 5 minutes
        self.result_chunk_profiles = [
            {"max_rows": 2000, "initial_rows": 2000, "batch_rows": 2000},
            {"max_rows": 20000, "initial_rows": 500, "batch_rows": 500},
            {"max_rows": 100000, "initial_rows": 400, "batch_rows": 900},
            {"max_rows": None, "initial_rows": 300, "batch_rows": 1200},
        ]
        self._default_result_chunk_profiles = copy.deepcopy(self.result_chunk_profiles)
        self.result_chunk_backpressure_ms = 30
        self.result_chunk_idle_interval_ms = 0
        self.result_chunk_inactive_tab_ms = 60
        self.process_refresh_debounce_ms = 50
        self._default_result_chunk_backpressure_ms = self.result_chunk_backpressure_ms
        self._default_result_chunk_idle_interval_ms = self.result_chunk_idle_interval_ms
        self._default_result_chunk_inactive_tab_ms = self.result_chunk_inactive_tab_ms

    def _normalize_positive_int(self, value, fallback, minimum=0):
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return int(fallback)
        if normalized < minimum:
            return int(fallback)
        return normalized

    def _normalize_chunk_profiles(self, profiles):
        normalized_profiles = []
        if not isinstance(profiles, list):
            return copy.deepcopy(self._default_result_chunk_profiles)

        for profile in profiles:
            if not isinstance(profile, dict):
                continue

            max_rows_value = profile.get("max_rows")
            if max_rows_value is None:
                max_rows = None
            else:
                try:
                    max_rows = int(max_rows_value)
                    if max_rows <= 0:
                        continue
                except (TypeError, ValueError):
                    continue

            initial_rows = self._normalize_positive_int(profile.get("initial_rows"), 500, minimum=1)
            batch_rows = self._normalize_positive_int(profile.get("batch_rows"), 500, minimum=1)
            normalized_profiles.append({
                "max_rows": max_rows,
                "initial_rows": initial_rows,
                "batch_rows": batch_rows,
            })

        if not normalized_profiles:
            return copy.deepcopy(self._default_result_chunk_profiles)

        def profile_sort_key(item):
            max_rows = item.get("max_rows")
            return (max_rows is None, max_rows if max_rows is not None else float("inf"))

        normalized_profiles.sort(key=profile_sort_key)
        return normalized_profiles

    def _normalize_process_status(self, status_text):
        return str(status_text or "").strip().upper()

    def _extract_query_table_name(self, query):
        table_context = resolve_writable_table_context(query)
        if table_context:
            return table_context.get("real_table_name")

        match = re.search(r"FROM\s+([\"\[\]\w\.]+)", query or "", re.IGNORECASE)
        if not match:
            return None
        extracted_table = match.group(1)
        table_name = extracted_table.replace('"', '').replace('[', '').replace(']', '')
        if "." in table_name:
            parts = table_name.split('.')
            return parts[-1]
        return table_name

    def _get_output_tabs_widget(self, tab_content):
        return output_tabs.get_output_tabs_widget(self, tab_content)

    def _ensure_output_tabs_widget(self, tab_content):
        return output_tabs.ensure_output_tabs_widget(self, tab_content)

    def _get_output_tab_container(self, tab_content, output_tab_index=None):
        return output_tabs.get_output_tab_container(self, tab_content, output_tab_index)

    def _get_result_table_for_tab(self, tab_content, output_tab_index=None):
        return output_tabs.get_result_table_for_tab(self, tab_content, output_tab_index)

    def _ensure_result_table_for_tab(self, tab_content, output_tab_index=None):
        return output_tabs.ensure_result_table_for_tab(self, tab_content, output_tab_index)

    def _create_output_table_view(self, tab_content):
        return output_tabs.create_output_table_view(self, tab_content)

    def create_output_tab(self, tab_content, title=None, activate=True):
        return output_tabs.create_output_tab(self, tab_content, title, activate)

    def add_output_tab_with_table_name(self, tab_content, query=None, table_name=None, activate=True):
        return output_tabs.add_output_tab_with_table_name(self, tab_content, query, table_name, activate)

    def _ensure_at_least_one_output_tab(self, tab_content):
        output_tabs.ensure_at_least_one_output_tab(self, tab_content)

    def _set_output_tab_title(self, tab_content, output_tab_index, query):
        output_tabs.set_output_tab_title(self, tab_content, output_tab_index, query)

    def _handle_output_tab_close(self, tab_content, index):
        output_tabs.handle_output_tab_close(self, tab_content, index)

    def serialize_output_tabs(self, tab_content):
        return output_tabs.serialize_output_tabs(self, tab_content)

    def restore_output_tabs(self, tab_content, output_data):
        output_tabs.restore_output_tabs(self, tab_content, output_data)

    def ensure_default_output_tab(self, tab_content):
        return output_tabs.ensure_default_output_tab(self, tab_content)

    def cleanup_tab_resources(self, tab_content):
        output_tabs.stop_all_chunk_loaders_for_tab(self, tab_content)

    def sync_row_action_state(self, tab_content=None):
        target_tab = tab_content or self.tab_widget.currentWidget()
        if not target_tab:
            return

        table_view = self._get_result_table_for_tab(target_tab)
        output_state = table_view.property("output_state") if table_view else {}
        is_enabled = bool((output_state or {}).get("is_editable"))

        for object_name in ("add_row_btn", "save_row_btn", "delete_row_btn"):
            button = target_tab.findChild(QWidget, object_name)
            if button:
                button.setEnabled(is_enabled)

    def _get_process_status_meta(self, status_text):
        return processes.get_process_status_meta(self, status_text)

    def _set_process_filter(self, tab_content, filter_key):
        processes.set_process_filter(self, tab_content, filter_key)

    def _update_process_summary_ui(self, target_tab, status_counts, total_count, visible_count):
        processes.update_process_summary_ui(self, target_tab, status_counts, total_count, visible_count)

    def _handle_process_cell_click(self, tab_content, index):
        processes.handle_process_cell_click(self, tab_content, index)

    def _handle_process_column_header_click(self, tab_content, column):
        processes.handle_process_column_header_click(self, tab_content, column)

    def _handle_process_row_header_click(self, tab_content, row):
        processes.handle_process_row_header_click(self, tab_content, row)

    def copy_current_result_table(self):
        clipboard.copy_current_result_table(self)


    def copy_result_with_header(self, table_view: QTableView):
        clipboard.copy_result_with_header(self, table_view)


    def paste_to_editor(self):
        clipboard.paste_to_editor(self)

    def _get_current_editor(self):
        return clipboard.get_current_editor(self)

    def delete_selected_row(self):
        row_crud.delete_selected_row(self)


    def model_to_dataframe(self, model):
        return row_crud.model_to_dataframe(self, model)

    def download_result(self, tab_content):
        row_crud.download_result(self, tab_content)



    def add_empty_row(self):
        row_crud.add_empty_row(self)


    
    def save_new_row(self):
        row_crud.save_new_row(self)

    def toggle_table_search(self):
        query_handler.toggle_table_search(self)

    def get_performance_snapshot(self):
        return perf_snapshot(self)

    def get_result_chunk_config(self):
        return {
            "profiles": copy.deepcopy(self.result_chunk_profiles),
            "backpressure_ms": int(self.result_chunk_backpressure_ms),
            "idle_interval_ms": int(self.result_chunk_idle_interval_ms),
            "inactive_tab_ms": int(self.result_chunk_inactive_tab_ms),
        }

    def update_result_chunk_config(self, profiles=None, backpressure_ms=None, idle_interval_ms=None, inactive_tab_ms=None):
        if profiles is not None:
            self.result_chunk_profiles = self._normalize_chunk_profiles(profiles)

        if backpressure_ms is not None:
            self.result_chunk_backpressure_ms = self._normalize_positive_int(backpressure_ms, self.result_chunk_backpressure_ms, minimum=1)

        if idle_interval_ms is not None:
            self.result_chunk_idle_interval_ms = self._normalize_positive_int(idle_interval_ms, self.result_chunk_idle_interval_ms, minimum=0)

        if inactive_tab_ms is not None:
            self.result_chunk_inactive_tab_ms = self._normalize_positive_int(inactive_tab_ms, self.result_chunk_inactive_tab_ms, minimum=1)

        return self.get_result_chunk_config()

    def reset_result_chunk_config(self):
        self.result_chunk_profiles = copy.deepcopy(self._default_result_chunk_profiles)
        self.result_chunk_backpressure_ms = int(self._default_result_chunk_backpressure_ms)
        self.result_chunk_idle_interval_ms = int(self._default_result_chunk_idle_interval_ms)
        self.result_chunk_inactive_tab_ms = int(self._default_result_chunk_inactive_tab_ms)
        return self.get_result_chunk_config()

    def _format_performance_snapshot_text(self, snapshot):
        header = [
            "Performance Snapshot (Results View)",
            f"Captured: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        if not snapshot:
            header.append("No metrics recorded yet.")
            return "\n".join(header)

        ordered_metric_names = sorted(snapshot.keys())
        for metric_name in ordered_metric_names:
            metric_values = snapshot.get(metric_name, {})
            parts = []
            for key in ["count", "last", "avg", "min", "max", "p95"]:
                value = metric_values.get(key)
                if value is None:
                    continue
                if isinstance(value, Number):
                    formatted = f"{float(value):.2f}"
                else:
                    formatted = str(value)
                parts.append(f"{key}={formatted}")
            details = ", ".join(parts) if parts else "no values"
            header.append(f"- {metric_name}: {details}")

        return "\n".join(header)

    def dump_performance_snapshot_to_messages(self, tab_content=None):
        target_tab = tab_content or self.tab_widget.currentWidget()
        if not target_tab:
            return

        message_view = target_tab.findChild(QTextEdit, "message_view")
        if message_view is None:
            return

        snapshot_text = self._format_performance_snapshot_text(self.get_performance_snapshot())
        previous_text = message_view.toPlainText().strip()
        if previous_text:
            message_view.append("\n" + "-" * 50)
        message_view.append(snapshot_text)
        scrollbar = message_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def clear_messages(self, tab_content=None):
        target_tab = tab_content or self.tab_widget.currentWidget()
        if not target_tab:
            return
            
        message_view = target_tab.findChild(QTextEdit, "message_view")
        if message_view:
            message_view.clear()
            self.status.showMessage("Messages cleared.", 2000)


    def handle_query_result(self, target_tab, conn_data, query, results, columns, column_specs, row_count, elapsed_time, is_select_query, output_mode="current", output_tab_index=None):
        query_handler.handle_query_result(self, target_tab, conn_data, query, results, columns, column_specs, row_count, elapsed_time, is_select_query, output_mode, output_tab_index)

    def add_connection_notification(self, conn_name):
        from widgets.results_view.notifications import add_connection_event
        from PySide6.QtWidgets import QTreeView
        target_tab = self.tab_widget.currentWidget()
        if not target_tab:
            return
            
        notif_view = target_tab.findChild(QTreeView, "notification_list_view")
        if notif_view:
            add_connection_event(notif_view, conn_name)
            # Auto switch removed per user request



    def handle_cell_edit(self, item, tab, table_view=None):
        query_handler.handle_cell_edit(self, item, tab, table_view)

    def _compact_data_type_label(self, data_type):
        return query_handler.compact_data_type_label(self, data_type)


    def stop_spinner(self, target_tab, success=True, target_index=0):
        if not target_tab:
            return
        stacked_widget = target_tab.findChild(QStackedWidget, "results_stacked_widget")
        results_info_bar = target_tab.findChild(QWidget, "resultsInfoBar")
        process_filter_bar = target_tab.findChild(QWidget, "processFilterBar")
        if stacked_widget:
            spinner_label = stacked_widget.findChild(QLabel, "spinner_label")
            if spinner_label and spinner_label.movie():
                spinner_label.movie().stop()
            header = target_tab.findChild(QWidget, "resultsHeader")
            buttons = header.findChildren(QPushButton)
            if success:
                stacked_widget.setCurrentIndex(target_index)
                if buttons: 
                    buttons[0].setChecked(target_index == 0) 
                    buttons[1].setChecked(target_index == 1) 
                    buttons[2].setChecked(target_index == 2)
                    buttons[3].setChecked(target_index == 3)
                if results_info_bar and process_filter_bar:
                    if target_index == 0:
                        if stacked_widget.widget(0).findChild(QTableView, "results_table"):
                            results_info_bar.show()
                        else:
                            # Hide toolbar if no results table is present or being shown
                            results_info_bar.hide()
                        self.sync_row_action_state(target_tab)
                        process_filter_bar.hide()
                    elif target_index == 3:
                        results_info_bar.hide()
                        process_filter_bar.show()
                    else:
                        results_info_bar.hide()
                        process_filter_bar.hide()
            else:
                stacked_widget.setCurrentIndex(1)
                if buttons: 
                    buttons[0].setChecked(False) 
                    buttons[1].setChecked(True)
                    buttons[2].setChecked(False)
                    buttons[3].setChecked(False)
                if results_info_bar:
                    results_info_bar.hide()
                if process_filter_bar:
                    process_filter_bar.hide()


    def update_page_label(self, target_tab, row_count):
        page_label = target_tab.findChild(QLabel, "page_label")
        if not page_label:
           return

        limit_val = getattr(target_tab, 'current_limit', 0)
        offset_val = getattr(target_tab, 'current_offset', 0)

        if row_count <= 0 or limit_val == 0:
           page_label.setText("Page 1")
           return

        current_page = (offset_val // limit_val) + 1
        page_label.setText(f"Page {current_page}")



    def show_results_context_menu(self, position):
        results_table = self.sender()
        if not results_table or not results_table.model():
          return

        menu = QMenu()
        export_action = QAction("Export Rows", self.main_window)
        export_action.triggered.connect(lambda: self.export_result_rows(results_table))
        menu.addAction(export_action)

        menu.exec(results_table.viewport().mapToGlobal(position))

      
    def export_result_rows(self, table_view):
        model = table_view.model()
        if not model:
          QMessageBox.warning(self.main_window, "No Data", "No results available to export.")
          return

        dialog = ExportDialog(self.main_window, "query_results.csv")
        if dialog.exec() != QDialog.DialogCode.Accepted:
          return

        options = dialog.get_options()
        
        if not options['filename']:
          QMessageBox.warning(self.main_window, "No Filename", "Export cancelled. No filename specified.")
          return
        # 🧪 Force an invalid export option to simulate an error
        # options["delimiter"] = None   # invalid delimiter will break df.to_csv()

        # if options["delimiter"] == ',':
        #     options["delimiter"] = None

        # --- Find connection name dynamically ---
        current_tab = self.tab_widget.currentWidget()
        db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
        conn_name = "Unknown"
        conn_id = None # --- MODIFICATION: (Previous change)
        
        if db_combo_box:
          index = db_combo_box.currentIndex()
          if index >= 0:
              conn_data = db_combo_box.itemData(index)
              conn_name = conn_data.get("short_name", "Unknown")
              conn_id = conn_data.get("id") # --- MODIFICATION: (Previous change)

        # --- Create Process info ---
        full_process_id = str(uuid.uuid4())
        short_id = full_process_id[:8]
        initial_data = {
           "pid": short_id,
           "type": "Export Data",
           "status": "Running",
           "server": conn_name,
           "object": "Query Results",
           "time_taken": "...",
           "start_time": datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
           "details": f"Exporting to {os.path.basename(options['filename'])}",
           # --- START MODIFICATION (Previous change) ---
           "_conn_id": conn_id
           # --- END MODIFICATION ---
        }

        signals = ProcessSignals()
        signals.started.connect(self.handle_process_started)
        signals.finished.connect(self.handle_process_finished)
        signals.error.connect(self.handle_process_error)
        emit_process_started(signals, short_id, initial_data)

        self.thread_pool.start(
          RunnableExportFromModel(short_id, model, options, signals)
        )
     
    def _initialize_processes_model(self, tab_content):
        processes.initialize_processes_model(self, tab_content)

            
    def switch_to_processes_view(self):
        processes.switch_to_processes_view(self)
    
    

    
    def handle_process_started(self, process_id, data):
        processes.handle_process_started(self, process_id, data)
    # change
    def handle_process_finished(self, process_id, message, time_taken, row_count):
        processes.handle_process_finished(self, process_id, message, time_taken, row_count)

    def handle_process_error(self, process_id, error_message):
        processes.handle_process_error(self, process_id, error_message)
    
    
    def refresh_processes_view(self):
        processes.refresh_processes_view(self)
        

    def get_current_tab_processes_model(self):
        return processes.get_current_tab_processes_model(self)

    def open_limit_offset_dialog(self, tab_content):
        """Opens a dialog to set Limit and Offset like pgAdmin."""
        dialog = QDialog(self.main_window)
        dialog.setWindowTitle("Query Options")
        dialog.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        # dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowMinMaxButtonsHint)
        dialog.setFixedSize(340, 160)
        # dialog.setWindowIcon(QIcon()) 
        
        # Apply the connection dialog styles
        dialog.setStyleSheet("""
            QDialog {
                background-color: #f6f8fb;
            }
            QSpinBox {
                min-height: 28px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background: white;
                padding-left: 6px;
                padding-right: 20px;
            }
            QSpinBox:focus {
                border: 1px solid #0078d4;
            }
            QPushButton {
                min-height: 28px;
                padding: 2px 14px;
                border: 1px solid #c4c9d4;
                background-color: #eef1f6;
                color: #1f2937;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #e3e8f2;
            }
            QPushButton:pressed {
                background-color: #d7deeb;
            }
            QPushButton#primaryButton {
                border: 1px solid #006cbe;
                background-color: #0078d4;
                color: #ffffff;
                font-weight: 600;
            }
            QPushButton#primaryButton:hover {
                background-color: #006cbe;
            }
            QPushButton#primaryButton:pressed {
                background-color: #005a9e;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 15)
        layout.setSpacing(15)
        
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(15)
        form.setVerticalSpacing(12)

        # Limit Input
        limit_spin = QSpinBox()
        limit_spin.setRange(0, 999999999) # 0 means no limit (logic handled below)
        limit_spin.setValue(int(getattr(tab_content, 'current_limit', 0) or 0))
        limit_spin.setSpecialValueText("No Limit") # If value is 0
        form.addRow("Rows Limit:", limit_spin)

        # Offset Input
        offset_spin = QSpinBox()
        offset_spin.setRange(0, 999999999)
        offset_spin.setValue(getattr(tab_content, 'current_offset', 0))
        form.addRow("Start Row (Offset):", offset_spin)
        
        layout.addLayout(form)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        
        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("primaryButton")
        ok_btn.clicked.connect(dialog.accept)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Update values in tab object
            new_limit = limit_spin.value()
            new_offset = offset_spin.value()
            
            tab_content.current_limit = new_limit if new_limit > 0 else 0
            tab_content.current_offset = new_offset
            
            # Refresh Display Label (Optional immediate update)
            rows_info_label = tab_content.findChild(QLabel, "rows_info_label")
            if rows_info_label:
                limit_text = str(new_limit) if new_limit > 0 else "All"
                rows_info_label.setText(f"Settings: Limit {limit_text}, Offset {new_offset}")

            # Sync to Worksheet Limit Dropdown
            rows_limit_combo = tab_content.findChild(QComboBox, "rows_limit_combo")
            if rows_limit_combo:
                # Temporarily block signals to avoid recursion if on_limit_change was still auto-executing
                rows_limit_combo.blockSignals(True)
                limit_str = str(new_limit) if new_limit > 0 else "No Limit"
                
                # If custom limit not in the list, add it numerically
                if rows_limit_combo.findText(limit_str) == -1:
                    insert_idx = 1
                    for i in range(1, rows_limit_combo.count()):
                        try:
                            if new_limit < int(rows_limit_combo.itemText(i)):
                                break
                        except ValueError:
                            pass
                        insert_idx += 1
                    rows_limit_combo.insertItem(insert_idx, limit_str)
                
                rows_limit_combo.setCurrentText(limit_str)
                rows_limit_combo.blockSignals(False)

    def eventFilter(self, watched, event):
        if watched.objectName() == "table_search_box" and event.type() == QEvent.Type.FocusOut:
            watched.hide()
            parent = watched.parent()
            if parent:
                btn = parent.findChild(QToolButton, "table_search_btn")
                if btn:
                    btn.show()
            return False
            
        return super().eventFilter(watched, event)

    def create_results_ui(self, tab_content):
        return ui.create_results_ui(self, tab_content)
