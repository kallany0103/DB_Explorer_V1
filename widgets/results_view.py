import os
import uuid
import datetime
import re
import sqlite3 as sqlite
import pandas as pd
import sqlparse
from functools import partial

from PyQt6.QtWidgets import (
    QApplication, QTableView, QMessageBox, QMenu, QComboBox, 
    QDialog, QFileDialog, QLineEdit, QToolButton, QStackedWidget,
    QWidget, QLabel, QPushButton, QTextEdit, QTreeView,
    QVBoxLayout, QHBoxLayout, QSplitter, QHeaderView, QAbstractItemView,
    QButtonGroup, QSizePolicy, QFormLayout, QSpinBox, QDialogButtonBox, 
    QFrame, QGroupBox, QInputDialog, QPlainTextEdit, QTabWidget,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem
)
from PyQt6.QtCore import (
    Qt, QObject, QTimer, QSize, QSortFilterProxyModel, pyqtSignal, QEvent
)
from PyQt6.QtGui import (
    QAction, QColor, QBrush, QStandardItemModel, QStandardItem, QMovie, QFont,
    QIcon, QKeySequence, QShortcut, QPalette
)

import db
from .explain_visualizer import ExplainVisualizer
from dialogs import ExportDialog
from workers import RunnableExportFromModel, ProcessSignals, FetchMetadataWorker, MetadataSignals


class ProcessRowDelegate(QStyledItemDelegate):
    """Draws status-based row background while preserving distinct cell/row/column selection behavior."""

    def __init__(self, status_meta, default_bg="#ffffff", parent=None):
        super().__init__(parent)
        self.status_meta = status_meta or {}
        self.default_bg = QColor(default_bg)
        self._status_column_cache = {}  # Cache {model_id -> column_index}

    def _get_status_column(self, model):
        """Get status column index, cached per model."""
        if not model or not hasattr(model, "columnCount"):
            return -1
        
        # Use model id for caching (Phase 3 optimization)
        model_id = id(model)
        if model_id in self._status_column_cache:
            return self._status_column_cache[model_id]
        
        # Lookup if not cached
        for column in range(model.columnCount()):
            header = str(model.headerData(column, Qt.Orientation.Horizontal) or "").upper()
            if "STATUS" in header:
                self._status_column_cache[model_id] = column
                return column
        
        self._status_column_cache[model_id] = -1
        return -1

    def paint(self, painter, option, index):
        source_model = index.model()
        source_index = index
        if hasattr(source_model, "mapToSource") and hasattr(source_model, "sourceModel"):
            source_index = source_model.mapToSource(index)
            source_model = source_model.sourceModel()

        status_col = self._get_status_column(source_model)
        status_text = ""
        if status_col >= 0:
            status_index = source_model.index(source_index.row(), status_col)
            status_text = str(status_index.data() or "").strip().upper()

        status_cfg = self.status_meta.get(status_text, None)
        bg_color = QColor(status_cfg.get("color")) if status_cfg else None

        is_item_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_row_selection = False
        is_col_selection = False
        if option.widget and option.widget.selectionModel():
            sel_model = option.widget.selectionModel()
            is_row_selection = sel_model.isRowSelected(index.row(), index.parent())
            is_col_selection = sel_model.isColumnSelected(index.column(), index.parent())

        painter.save()
        if is_item_selected:
            selection_fill = QColor("#8f959e")
            if is_row_selection or is_col_selection:
                selection_fill.setAlpha(235)
            painter.fillRect(option.rect, selection_fill)
        elif bg_color:
            row_bg = QColor(bg_color)
            painter.fillRect(option.rect, row_bg)

        paint_option = QStyleOptionViewItem(option)
        paint_option.state &= ~QStyle.StateFlag.State_Selected
        paint_option.state &= ~QStyle.StateFlag.State_MouseOver
        paint_option.state &= ~QStyle.StateFlag.State_HasFocus

        if index.column() == status_col:
            paint_option.displayAlignment = Qt.AlignmentFlag.AlignCenter

        use_light_text = is_item_selected

        if use_light_text:
            paint_option.palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        else:
            paint_option.palette.setColor(QPalette.ColorRole.Text, QColor("#1f2937"))

        super().paint(painter, paint_option, index)
        painter.restore()


class FlatSelectionDelegate(QStyledItemDelegate):
    """Paints result-table selection like the process tab (full-cell blue, no inner focus frame)."""

    def __init__(self, selection_color="#8f959e", parent=None):
        super().__init__(parent)
        self.selection_color = QColor(selection_color)

    def paint(self, painter, option, index):
        is_item_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_item_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        is_editing_cell = False
        is_row_selection = False
        is_col_selection = False
        if option.widget and option.widget.selectionModel():
            sel_model = option.widget.selectionModel()
            is_row_selection = sel_model.isRowSelected(index.row(), index.parent())
            is_col_selection = sel_model.isColumnSelected(index.column(), index.parent())
            if option.widget.state() == QAbstractItemView.State.EditingState:
                current_index = option.widget.currentIndex()
                is_editing_cell = (
                    current_index.isValid()
                    and current_index.row() == index.row()
                    and current_index.column() == index.column()
                )

        painter.save()
        if is_item_selected and not is_editing_cell:
            fill = QColor(self.selection_color)
            if is_row_selection or is_col_selection:
                fill.setAlpha(235)
            painter.fillRect(option.rect, fill)
        elif is_item_hovered and not is_editing_cell:
            hover_fill = QColor(self.selection_color)
            hover_fill.setAlpha(235)
            painter.fillRect(option.rect, hover_fill)
        elif is_editing_cell:
            border_color = QColor("#a9a9a9")
            painter.setPen(border_color)
            painter.drawRect(option.rect.adjusted(0, 0, -1, -1))

        paint_option = QStyleOptionViewItem(option)
        paint_option.state &= ~QStyle.StateFlag.State_Selected
        paint_option.state &= ~QStyle.StateFlag.State_MouseOver
        paint_option.state &= ~QStyle.StateFlag.State_HasFocus
        if is_editing_cell:
            paint_option.text = ""
        if (is_item_selected or is_item_hovered) and not is_editing_cell:
            paint_option.palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        super().paint(painter, paint_option, index)
        painter.restore()

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.setFrame(False)
            editor.setStyleSheet("QLineEdit { border: 1px solid #a9a9a9; outline: none; border-radius: 0px; background-color: #ffffff; padding: 0 2px; }")
        return editor

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

class ResultsManager(QObject):
    PROCESS_STATUS_META = {
        "RUNNING": {"label": "Running", "color": "#FFF4CC", "priority": 1},
        "SUCCESSFULL": {"label": "Successfull", "color": "#E8F5E9", "priority": 2},
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

    def _normalize_process_status(self, status_text):
        return str(status_text or "").strip().upper()

    def _extract_query_table_name(self, query):
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
        if not tab_content:
            return None
        return tab_content.findChild(QTabWidget, "output_tabs")

    def _ensure_output_tabs_widget(self, tab_content):
        output_tabs = self._get_output_tabs_widget(tab_content)
        if output_tabs:
            return output_tabs

        results_stack = tab_content.findChild(QStackedWidget, "results_stacked_widget")
        if not results_stack:
            return None

        old_page_zero = results_stack.widget(0)

        output_tabs = QTabWidget()
        output_tabs.setObjectName("output_tabs")
        output_tabs.setTabsClosable(True)
        output_tabs.setMovable(False)
        output_tabs.setTabBarAutoHide(False)
        output_tabs.setDocumentMode(True)
        output_tabs.tabCloseRequested.connect(lambda index: self._handle_output_tab_close(tab_content, index))

        output_container = QWidget()
        output_layout = QVBoxLayout(output_container)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(0)

        existing_table = old_page_zero.findChild(QTableView, "results_table") if old_page_zero else None
        if existing_table:
            existing_table.setParent(None)
            output_layout.addWidget(existing_table)
        else:
            output_layout.addWidget(self._create_output_table_view(tab_content))

        output_tabs.addTab(output_container, "Result 1")
        output_tabs.setCurrentIndex(0)

        results_stack.insertWidget(0, output_tabs)
        if old_page_zero is not None:
            results_stack.removeWidget(old_page_zero)
            old_page_zero.deleteLater()

        return output_tabs

    def _get_output_tab_container(self, tab_content, output_tab_index=None):
        output_tabs = self._ensure_output_tabs_widget(tab_content)
        if not output_tabs:
            return None
        if output_tab_index is not None and 0 <= output_tab_index < output_tabs.count():
            return output_tabs.widget(output_tab_index)
        return output_tabs.currentWidget()

    def _get_result_table_for_tab(self, tab_content, output_tab_index=None):
        output_container = self._get_output_tab_container(tab_content, output_tab_index)
        if not output_container:
            return None
        return output_container.findChild(QTableView, "results_table")

    def _ensure_result_table_for_tab(self, tab_content, output_tab_index=None):
        output_tabs = self._ensure_output_tabs_widget(tab_content)
        if not output_tabs:
            return None, None

        self._ensure_at_least_one_output_tab(tab_content)

        if output_tab_index is not None and 0 <= output_tab_index < output_tabs.count():
            output_tabs.setCurrentIndex(output_tab_index)

        output_container = output_tabs.currentWidget()
        if not output_container:
            # Rebuild one tab defensively
            self._ensure_at_least_one_output_tab(tab_content)
            output_container = output_tabs.currentWidget()
            if not output_container:
                return None, None

        table_view = output_container.findChild(QTableView, "results_table")
        if table_view is None:
            output_layout = output_container.layout()
            if output_layout is None:
                output_layout = QVBoxLayout(output_container)
                output_layout.setContentsMargins(0, 0, 0, 0)
                output_layout.setSpacing(0)
            table_view = self._create_output_table_view(tab_content)
            output_layout.addWidget(table_view)

        return table_view, output_tabs.currentIndex()

    def _create_output_table_view(self, tab_content):
        table_view = QTableView()
        table_view.setObjectName("results_table")
        table_view.setAlternatingRowColors(True)
        table_view.setMouseTracking(True)
        table_view.viewport().setMouseTracking(True)
        table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table_view.horizontalHeader().setSectionsClickable(True)
        table_view.verticalHeader().setSectionsClickable(True)
        table_view.verticalHeader().setDefaultSectionSize(28)
        table_view.setItemDelegate(FlatSelectionDelegate(parent=table_view))
        table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table_view.customContextMenuRequested.connect(self.show_results_context_menu)
        table_view.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)

        output_state = {
            "table_name": None,
            "real_table_name": None,
            "schema_name": None,
            "column_names": [],
            "modified_coords": set(),
            "new_row_index": None,
            "cached_proxy_model": None,
        }
        table_view.setProperty("output_state", output_state)
        return table_view

    def create_output_tab(self, tab_content, title=None, activate=True):
        output_tabs = self._ensure_output_tabs_widget(tab_content)
        if not output_tabs:
            return None

        output_container = QWidget()
        output_layout = QVBoxLayout(output_container)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(0)

        table_view = self._create_output_table_view(tab_content)
        output_layout.addWidget(table_view)

        default_title = title or f"Result {output_tabs.count() + 1}"
        new_index = output_tabs.addTab(output_container, default_title)
        if activate:
            output_tabs.setCurrentIndex(new_index)
        return new_index

    def _ensure_at_least_one_output_tab(self, tab_content):
        output_tabs = self._ensure_output_tabs_widget(tab_content)
        if output_tabs and output_tabs.count() == 0:
            output_container = QWidget()
            output_layout = QVBoxLayout(output_container)
            output_layout.setContentsMargins(0, 0, 0, 0)
            output_layout.setSpacing(0)
            table_view = self._create_output_table_view(tab_content)
            output_layout.addWidget(table_view)
            output_tabs.addTab(output_container, "Result 1")
            output_tabs.setCurrentIndex(0)

    def _set_output_tab_title(self, tab_content, output_tab_index, query):
        output_tabs = self._ensure_output_tabs_widget(tab_content)
        if not output_tabs or output_tab_index is None:
            return
        if output_tab_index < 0 or output_tab_index >= output_tabs.count():
            return

        table_name = self._extract_query_table_name(query)
        if not table_name:
            table_name = "Result"

        display_number = output_tab_index + 1
        output_tabs.setTabText(output_tab_index, f"{table_name} {display_number}")

    def _handle_output_tab_close(self, tab_content, index):
        output_tabs = self._ensure_output_tabs_widget(tab_content)
        if not output_tabs:
            return
        if output_tabs.count() <= 1:
            return
        output_tabs.removeTab(index)
        if output_tabs.count() == 0:
            self.create_output_tab(tab_content, title="Result 1", activate=True)

    def serialize_output_tabs(self, tab_content):
        output_tabs = self._ensure_output_tabs_widget(tab_content)
        if not output_tabs:
            return {"tabs": ["Result 1"], "active_index": 0}

        tab_titles = [output_tabs.tabText(i) or f"Result {i + 1}" for i in range(output_tabs.count())]
        active_index = output_tabs.currentIndex() if output_tabs.currentIndex() >= 0 else 0
        return {
            "tabs": tab_titles if tab_titles else ["Result 1"],
            "active_index": active_index,
        }

    def restore_output_tabs(self, tab_content, output_data):
        output_tabs = self._ensure_output_tabs_widget(tab_content)
        if not output_tabs:
            return

        output_tabs.blockSignals(True)
        output_tabs.clear()

        saved_titles = []
        if isinstance(output_data, dict):
            saved_titles = output_data.get("tabs", []) or []

        if not saved_titles:
            saved_titles = ["Result 1"]

        for title in saved_titles:
            self.create_output_tab(tab_content, title=str(title), activate=False)

        active_index = 0
        if isinstance(output_data, dict):
            active_index = output_data.get("active_index", 0)
        if active_index < 0 or active_index >= output_tabs.count():
            active_index = 0
        output_tabs.setCurrentIndex(active_index)
        output_tabs.blockSignals(False)

    def ensure_default_output_tab(self, tab_content):
        output_tabs = self._ensure_output_tabs_widget(tab_content)
        if not output_tabs:
            return None
        return output_tabs

    def _get_process_status_meta(self, status_text):
        status_key = self._normalize_process_status(status_text)
        return self.PROCESS_STATUS_META.get(status_key, self.DEFAULT_PROCESS_STATUS_META)

    def _set_process_filter(self, tab_content, filter_key):
        tab_content.process_status_filter = filter_key
        self.refresh_processes_view()

    def _update_process_summary_ui(self, target_tab, status_counts, total_count, visible_count):
        filter_buttons = getattr(target_tab, "process_filter_buttons", {})
        if not filter_buttons:
            return

        all_count = total_count
        running_count = status_counts.get("RUNNING", 0)
        success_count = status_counts.get("SUCCESSFULL", 0)
        warning_count = status_counts.get("WARNING", 0)
        error_count = status_counts.get("ERROR", 0)

        if "ALL" in filter_buttons:
            filter_buttons["ALL"].setText(f"All ({all_count})")
        if "RUNNING" in filter_buttons:
            filter_buttons["RUNNING"].setText(f"Running ({running_count})")
        if "SUCCESSFULL" in filter_buttons:
            filter_buttons["SUCCESSFULL"].setText(f"Successfull ({success_count})")
        if "WARNING" in filter_buttons:
            filter_buttons["WARNING"].setText(f"Warning ({warning_count})")
        if "ERROR" in filter_buttons:
            filter_buttons["ERROR"].setText(f"Error ({error_count})")

    def _handle_process_cell_click(self, tab_content, index):
        if not index.isValid():
            return

        processes_view = tab_content.findChild(QTableView, "processes_view")
        if not processes_view:
            return

        model = processes_view.model()
        if not model:
            return

        selection_model = processes_view.selectionModel()
        is_row_selection = selection_model.isRowSelected(index.row(), index.parent()) if selection_model else False
        is_col_selection = selection_model.isColumnSelected(index.column(), index.parent()) if selection_model else False

        if is_row_selection:
            selection_mode = "Row"
        elif is_col_selection:
            selection_mode = "Column"
        else:
            selection_mode = "Cell"

        column_name = str(model.headerData(index.column(), Qt.Orientation.Horizontal) or f"Col {index.column() + 1}")
        message = f"{selection_mode} selected: R{index.row() + 1}, C{index.column() + 1} ({column_name})"

    def _handle_process_column_header_click(self, tab_content, column):
        processes_view = tab_content.findChild(QTableView, "processes_view")
        if not processes_view:
            return

        processes_view.selectColumn(column)

    def _handle_process_row_header_click(self, tab_content, row):
        processes_view = tab_content.findChild(QTableView, "processes_view")
        if not processes_view:
            return

        processes_view.selectRow(row)

    def copy_current_result_table(self):
        tab = self.tab_widget.currentWidget()
        if not tab:
           return

        table_view = self._get_result_table_for_tab(tab)
        if not table_view:
           return

        self.copy_result_with_header(table_view)


    def copy_result_with_header(self, table_view: QTableView):
        model = table_view.model()
        sel = table_view.selectionModel()

        if not model or not sel:
           return

        rows = []

        selected_rows = sel.selectedRows()
        selected_indexes = sel.selectedIndexes()

    # ---------- ROW SELECTION (pgAdmin default) ----------
        if selected_rows:
           columns = range(model.columnCount())

        # Header
           header = [
               str(model.headerData(col, Qt.Orientation.Horizontal) or "")
               for col in columns
            ]
           rows.append("\t".join(header))

        # Data
           for r in selected_rows:
               row = r.row()
               row_data = [
                str(model.index(row, col).data() or "")
                for col in columns
            ]
               rows.append("\t".join(row_data))

    # ---------- CELL SELECTION ----------
        elif selected_indexes:
            selected_indexes = sorted(
             selected_indexes, key=lambda x: (x.row(), x.column())
           )

            columns = sorted({i.column() for i in selected_indexes})

            header = [
            str(model.headerData(col, Qt.Orientation.Horizontal) or "")
            for col in columns
        ]
            rows.append("\t".join(header))

            current_row = selected_indexes[0].row()
            row_data = []

            for idx in selected_indexes:
                if idx.row() != current_row:
                  rows.append("\t".join(row_data))
                  row_data = []
                  current_row = idx.row()

                row_data.append(str(idx.data() or ""))

            rows.append("\t".join(row_data))

        else:
           return

    # 🔥 THIS LINE IS THE MAGIC
        QApplication.clipboard().setText("\n".join(rows))


    def paste_to_editor(self):
        editor = self._get_current_editor()
        if editor:
           editor.paste()

    def _get_current_editor(self):
        """Helper to get the current editor from the active tab."""
        # This was not in the snippet but implies existence.
        # Assuming it tries to find 'query_editor'
        current_tab = self.tab_widget.currentWidget()
        if not current_tab: return None
        # Try finding CodeEditor first if imported, else QPlainTextEdit
        editor = current_tab.findChild(QTextEdit, "query_editor") # simplified
        if not editor:
             # Try other types if needed, or check how main window does it
             # For now return None or look for 'query_editor' by object name
             pass
        return editor

    def delete_selected_row(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
            return

        table_view = self._get_result_table_for_tab(current_tab)
        if not table_view:
            return

        output_state = table_view.property("output_state") or {}
        table_name = output_state.get("table_name")
        
        if not table_name:
            QMessageBox.warning(self.main_window, "Warning", "Cannot determine table name. Please run a SELECT query first.")
            return

        display_model = table_view.model()
        selection_model = table_view.selectionModel()
        if not display_model or not selection_model:
            return

        if isinstance(display_model, QSortFilterProxyModel):
            source_model = display_model.sourceModel()
        else:
            source_model = display_model

        selected_source_rows = set()

        for idx in selection_model.selectedRows():
            if isinstance(display_model, QSortFilterProxyModel):
                idx = display_model.mapToSource(idx)
            selected_source_rows.add(idx.row())

        if not selected_source_rows:
            for idx in selection_model.selectedIndexes():
                if isinstance(display_model, QSortFilterProxyModel):
                    idx = display_model.mapToSource(idx)
                selected_source_rows.add(idx.row())

        if not selected_source_rows:
            QMessageBox.warning(self.main_window, "Warning", "Please select a row to delete.")
            return

        reply = QMessageBox.question(
            self.main_window, 
            'Confirm Deletion',
            f"Are you sure you want to delete {len(selected_source_rows)} row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        
        db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
        conn_data = db_combo_box.currentData()
        if not conn_data:
            QMessageBox.critical(self.main_window, "Error", "No active database connection found.")
            return

        db_code = (conn_data.get('code') or conn_data.get('db_type', '')).upper()
        deleted_count = 0
        errors = []

        conn = None
        try:
            
            if db_code == 'POSTGRES':
                conn = db.create_postgres_connection(**{k: v for k, v in conn_data.items() if k in ['host', 'port', 'database', 'user', 'password']})
            elif 'SQLITE' in str(db_code):
                conn = db.create_sqlite_connection(conn_data.get('db_path'))
            elif 'SERVICENOW' in str(db_code):
                conn = db.create_servicenow_connection(conn_data)
            
            if not conn:
                QMessageBox.critical(self.main_window, "Error", "Could not create database connection.")
                return

            cursor = conn.cursor()

            for row_idx in sorted(selected_source_rows, reverse=True):
                
                item = source_model.item(row_idx, 0)
                if not item: continue
                
                item_data = item.data(Qt.ItemDataRole.UserRole)
                pk_col = item_data.get("pk_col")
                pk_val = item_data.get("pk_val")

                if not pk_col or pk_val is None:
                    errors.append(f"Row {row_idx + 1}: No Primary Key found. Cannot delete safely.")
                    continue

                try:
                    sql = ""
                    if db_code == 'POSTGRES':
                        sql = f'DELETE FROM {table_name} WHERE "{pk_col}" = %s'
                        cursor.execute(sql, (pk_val,))
                    elif 'SQLITE' in str(db_code):
                        sql = f'DELETE FROM {table_name} WHERE "{pk_col}" = ?'
                        cursor.execute(sql, (pk_val,))
                    elif 'SERVICENOW' in str(db_code):
                        sql = f"DELETE FROM {table_name} WHERE {pk_col} = '{pk_val}'"
                        cursor.execute(sql)
                    
                    
                    source_model.removeRow(row_idx)
                    deleted_count += 1

                except Exception as inner_e:
                    errors.append(f"Row {row_idx + 1} Error: {str(inner_e)}")

            conn.commit()
            conn.close()

        except Exception as e:
            QMessageBox.critical(self.main_window, "Database Error", str(e))
            if conn: conn.close()
            return

        
        if deleted_count > 0:
            self.status.showMessage(f"Successfully deleted {deleted_count} row(s).", 3000)
            QMessageBox.information(self.main_window, "Success", f"Successfully deleted {deleted_count} row(s).")
            
        
        if errors:
            QMessageBox.warning(self.main_window, "Deletion Errors", "\n".join(errors[:5]))


    def model_to_dataframe(self, model):
        rows = model.rowCount()
        cols = model.columnCount()

        headers = [
           model.headerData(c, Qt.Orientation.Horizontal)
           for c in range(cols)
        ]

        data = []
        for r in range(rows):
           row = []
           for c in range(cols):
              index = model.index(r, c)
              row.append(model.data(index))
           data.append(row)

        return pd.DataFrame(data, columns=headers)

    def download_result(self, tab_content):
        table = self._get_result_table_for_tab(tab_content)
        if not table or not table.model():
           QMessageBox.warning(self.main_window, "No Data", "No result data to download")
           return

        model = table.model()
        df = self.model_to_dataframe(model)

        if df.empty:
           QMessageBox.warning(self.main_window, "No Data", "Result is empty")
           return

        file_path, selected_filter = QFileDialog.getSaveFileName(
           self.main_window,
           "Download Result",
           "query_result",
           "CSV (*.csv);;Excel (*.xlsx)"
           )

        if not file_path:
           return

        try:
           if file_path.endswith(".csv"):
              df.to_csv(file_path, index=False)
           elif file_path.endswith(".xlsx"):
              df.to_excel(file_path, index=False)

           QMessageBox.information(
              self.main_window,
              "Success",
              f"Result downloaded successfully:\n{file_path}"
            )

        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", str(e))



    def add_empty_row(self):
        tab = self.tab_widget.currentWidget()
        if not tab: return

        table = self._get_result_table_for_tab(tab)
        if not table:
            return
        model = table.model()
        if isinstance(model, QSortFilterProxyModel):
            model = model.sourceModel()
        

        if not model:
           return

        row = model.rowCount()
        model.insertRow(row)
        
        output_state = table.property("output_state") or {}
        output_state["new_row_index"] = row
        table.setProperty("output_state", output_state)

        table.scrollToBottom()
        table.setCurrentIndex(model.index(row, 0))
        table.edit(model.index(row, 0))


    
    def save_new_row(self):
        """
        Handles saving BOTH new rows (INSERT) and modified cells (UPDATE).
        """
        tab = self.tab_widget.currentWidget()
        if not tab: return
        
        saved_any = False
        update_popup_shown = False
        db_combo_box = tab.findChild(QComboBox, "db_combo_box")
        conn_data = db_combo_box.currentData()
        if not conn_data: return
        
        table = self._get_result_table_for_tab(tab)
        if not table:
            return
        output_state = table.property("output_state") or {}
        model = table.model()
        if isinstance(model, QSortFilterProxyModel):
            model = model.sourceModel()

        # ---------------------------------------------------------
        # PART 1: Handle INSERT (New Rows)
        # ---------------------------------------------------------
        if output_state.get("new_row_index") is not None:
            if not output_state.get("table_name") or not output_state.get("column_names"):
                 QMessageBox.warning(self.main_window, "Error", "Table context missing.")
            else:
                row_idx = output_state["new_row_index"]
                values = []
                for col_idx in range(model.columnCount()):
                    item = model.item(row_idx, col_idx)
                    val = item.text() if item else None
                    if val == '': val = None
                    values.append(val)

                cols_str = ", ".join([f'"{c}"' for c in output_state["column_names"]])
                db_code = (conn_data.get('code') or conn_data.get('db_type', '')).upper()
                
                sql = ""
                conn = None

                try:
                    if db_code == 'POSTGRES':
                        placeholders = ", ".join(["%s"] * len(values))
                        sql = f'INSERT INTO {output_state["table_name"]} ({cols_str}) VALUES ({placeholders})'
                        conn = db.create_postgres_connection(**{k: v for k, v in conn_data.items() if k in ['host', 'port', 'database', 'user', 'password']})
                        
                    elif 'SQLITE' in str(db_code): 
                        placeholders = ", ".join(["?"] * len(values))
                        sql = f'INSERT INTO {output_state["table_name"]} ({cols_str}) VALUES ({placeholders})'
                        conn = db.create_sqlite_connection(conn_data.get('db_path'))
                    

                    elif 'SERVICENOW' in str(db_code):
                        placeholders = ", ".join(["?"] * len(values))
                        # ServiceNow-
                        sql = f'INSERT INTO {output_state["table_name"]} ({cols_str}) VALUES ({placeholders})'
                        conn = db.create_servicenow_connection(conn_data)
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute(sql, values)
                        conn.commit()
                        conn.close()
                        output_state["new_row_index"] = None
                        table.setProperty("output_state", output_state)
                        saved_any = True
                        
                except Exception as e:
                    QMessageBox.critical(self.main_window, "Insert Error", f"Failed to insert row:\n{str(e)}")

        # ---------------------------------------------------------
        # PART 2: Handle UPDATE (Modified Cells)
        # ---------------------------------------------------------
        modified_coords = output_state.get("modified_coords", set())
        updates_count = 0
        update_errors = []
        if modified_coords:
            coords_to_process = list(modified_coords)
            db_code = (conn_data.get('code') or conn_data.get('db_type', '')).upper()
            conn = None

            try:
                if db_code == 'POSTGRES':
                    conn = db.create_postgres_connection(**{k: v for k, v in conn_data.items() if k in ['host', 'port', 'database', 'user', 'password']})
                elif 'SQLITE' in str(db_code):
                    conn = db.create_sqlite_connection(conn_data.get('db_path'))
                elif 'SERVICENOW' in str(db_code):
                    conn = db.create_servicenow_connection(conn_data)

                if not conn:
                    raise Exception("Could not create database connection for updates.")

                cursor = conn.cursor()
                table_name_for_update = output_state.get("table_name")

                for row, col in coords_to_process:
                    item = model.item(row, col)
                    if not item:
                        continue

                    edit_data = item.data(Qt.ItemDataRole.UserRole) or {}
                    pk_col = edit_data.get("pk_col")
                    pk_val = edit_data.get("pk_val")
                    col_name = edit_data.get("col_name")
                    new_val = item.text()
                    val_to_update = None if new_val == '' else new_val

                    if not table_name_for_update:
                        update_errors.append("Missing table context for update.")
                        continue
                    if not pk_col or pk_val is None:
                        update_errors.append(f"Missing PK for column {col_name}")
                        continue

                    try:
                        if db_code == 'POSTGRES':
                            sql = f'UPDATE {table_name_for_update} SET "{col_name}" = %s WHERE "{pk_col}" = %s'
                            cursor.execute(sql, (val_to_update, pk_val))
                        elif 'SQLITE' in str(db_code):
                            sql = f'UPDATE {table_name_for_update} SET "{col_name}" = ? WHERE "{pk_col}" = ?'
                            cursor.execute(sql, (val_to_update, pk_val))
                        elif 'SERVICENOW' in str(db_code):
                            sql = f"UPDATE {table_name_for_update} SET {col_name} = ? WHERE {pk_col} = ?"
                            cursor.execute(sql, (val_to_update, pk_val))
                        else:
                            update_errors.append(f"Unsupported DB type for updates: {db_code}")
                            continue

                        if hasattr(cursor, "rowcount") and cursor.rowcount == 0:
                            update_errors.append(f"No row updated for PK '{pk_col}'={pk_val}")
                            continue

                        edit_data['orig_val'] = new_val
                        item.setData(edit_data, Qt.ItemDataRole.UserRole)
                        item.setBackground(QColor(Qt.GlobalColor.white))
                        if (row, col) in modified_coords:
                            modified_coords.remove((row, col))
                        updates_count += 1
                    except Exception as inner_e:
                        update_errors.append(str(inner_e))

                conn.commit()
                if updates_count > 0:
                    saved_any = True

            except Exception as e:
                QMessageBox.critical(self.main_window, "Connection Error", f"Failed to update rows:\n{str(e)}")
            finally:
                if conn:
                    conn.close()

            output_state["modified_coords"] = modified_coords
            table.setProperty("output_state", output_state)

            if updates_count > 0:
                update_popup_shown = True
                QMessageBox.information(self.main_window, "Update Success", f"Updated {updates_count} value(s) successfully.")
            elif coords_to_process:
                QMessageBox.warning(self.main_window, "Update Failed", "Update failed. No values were updated.")

            if update_errors:
                QMessageBox.warning(self.main_window, "Update Details", "\n".join(update_errors[:8]))

        # ---------------------------------------------------------
        # Final Feedback
        # ---------------------------------------------------------
        if saved_any:
            self.status.showMessage("Changes saved successfully!", 3000)
            if not update_popup_shown:
                QMessageBox.information(self.main_window, "Success", "Changes saved successfully!")
        elif output_state.get("new_row_index") is None and not modified_coords:
            self.status.showMessage("No changes to save.", 3000)

    def toggle_table_search(self):
        """Show/expand the table search box and hide the button."""
        tab = self.tab_widget.currentWidget()
        if not tab: return
        
        search_box = tab.findChild(QLineEdit, "table_search_box")
        search_btn = tab.findChild(QToolButton, "table_search_btn")
        
        if search_box and search_btn:
            search_btn.hide()
            search_box.show()
            search_box.setFocus()


    def handle_query_result(self, target_tab, conn_data, query, results, columns, row_count, elapsed_time, is_select_query, output_mode="current", output_tab_index=None):
        
        # Stop timers
        if target_tab in self.tab_timers:
                self.tab_timers[target_tab]["timer"].stop(); self.tab_timers[target_tab]["timeout_timer"].stop(); del self.tab_timers[target_tab]

        self.save_query_to_history(conn_data, query, "Success", row_count, elapsed_time)

        # Get widgets
        self._ensure_at_least_one_output_tab(target_tab)
        if output_mode == "new" and output_tab_index is None:
            output_tab_index = self.create_output_tab(target_tab, activate=True)

        if output_tab_index is not None:
            output_tabs = self._get_output_tabs_widget(target_tab)
            if output_tabs and 0 <= output_tab_index < output_tabs.count():
                output_tabs.setCurrentIndex(output_tab_index)

        table_view, resolved_output_index = self._ensure_result_table_for_tab(target_tab, output_tab_index)
        if not table_view:
            message_view = target_tab.findChild(QTextEdit, "message_view")
            if message_view:
                message_view.append("Error rendering query result:\n\nOutput table container is unavailable.")
            tab_status_label = target_tab.findChild(QLabel, "tab_status_label")
            if tab_status_label:
                tab_status_label.setText("Error rendering query result")
            self.stop_spinner(target_tab, success=False)
            return

        output_state = table_view.property("output_state") or {}
        message_view = target_tab.findChild(QTextEdit, "message_view")
        tab_status_label = target_tab.findChild(QLabel, "tab_status_label")
        rows_info_label = target_tab.findChild(QLabel, "rows_info_label")
        
        # Access Result Stack
        results_stack = target_tab.findChild(QStackedWidget, "results_stacked_widget")
        results_info_bar = target_tab.findChild(QWidget, "resultsInfoBar")

        if message_view:
            message_view.clear()

        if is_select_query:
             # Check for Explain Analyze Result
            if query.upper().strip().startswith("EXPLAIN (ANALYZE,"):
                try:
                    # Result is usually [[json_data]]
                    if results and len(results) > 0 and len(results[0]) > 0:
                        json_data = results[0][0]
                        # Get visualizer
                        results_stack = target_tab.findChild(QStackedWidget, "results_stacked_widget")
                        explain_visualizer = results_stack.findChild(ExplainVisualizer)
                        if explain_visualizer:
                            explain_visualizer.load_plan(json_data)
                        
                        self.stop_spinner(target_tab, success=True, target_index=5) # Explain tab
                        
                        msg = f"Explain Analyze executed successfully.\nTime: {elapsed_time:.2f} sec"
                        status = f"Explain Analyze executed | Time: {elapsed_time:.2f} sec"
                        
                        # Update message view and status
                        if message_view:
                            previous_text = message_view.toPlainText()
                            if previous_text: message_view.append("\n" + "-"*50 + "\n")
                            message_view.append(msg)
                        if tab_status_label: tab_status_label.setText(status)
                        self.status_message_label.setText("Ready")

                        # Cleanup
                        if target_tab in self.running_queries: del self.running_queries[target_tab]
                        if not self.running_queries: self.cancel_action.setEnabled(False)
                        return
                except Exception as e:
                    print(f"Error parsing explain result: {e}")
                    # Fall through to normal display if parsing fails


        # --- Robust Query Type Detection ---
        match_query = re.sub(r'--.*?\n|/\*.*?\*/', '', query, flags=re.DOTALL).strip().upper()
        first_word = match_query.split()[0] if match_query.split() else ""
        
        q_type_parsed = ""
        parsed = sqlparse.parse(query)
        if parsed:
            for statement in parsed:
                t = statement.get_type().upper()
                if t != 'UNKNOWN':
                    q_type_parsed = t
                    break
        
        q_type = q_type_parsed if q_type_parsed and q_type_parsed != 'UNKNOWN' else first_word
        
        # Structural commands (DDL)
        is_structural = q_type in ["CREATE", "DROP", "ALTER", "TRUNCATE", "GRANT", "REVOKE", "COMMENT", "RENAME"]
        
        # SELECT check
        is_select = q_type == "SELECT" or first_word == "SELECT"
        
        # --- DECIDE WHICH TAB TO OPEN ---
        final_tab_index = 0 # Default to Output

        # Condition: If it is NOT structural AND (it is Select OR has columns) -> Show Output Tab (0)
        if not is_structural and (is_select or (columns and len(columns) > 0)):
            final_tab_index = 0
            output_state["column_names"] = list(columns)
            output_state["modified_coords"] = set()
            output_state["new_row_index"] = None

            # Extract table name logic
            match = re.search(r"FROM\s+([\"\[\]\w\.]+)", query, re.IGNORECASE)
            if match:
                extracted_table = match.group(1)
                output_state["table_name"] = extracted_table.replace('"', '').replace('[', '').replace(']', '')
                if "." in output_state["table_name"]:
                    parts = output_state["table_name"].split('.')
                    output_state["schema_name"] = parts[0]
                    output_state["real_table_name"] = parts[1]
                else:
                    output_state["schema_name"] = None
                    output_state["real_table_name"] = output_state["table_name"]
            else:
                output_state["table_name"] = None
                output_state["real_table_name"] = None
                output_state["schema_name"] = None

            # Row count logic
            current_offset = getattr(target_tab, 'current_offset', 0)
            if rows_info_label:
                if row_count > 0:
                    start_row = current_offset + 1
                    end_row = current_offset + row_count
                    rows_info_label.setText(f"Showing rows {start_row} - {end_row}")
                else:
                    rows_info_label.setText("No rows returned")
            
            page_label = target_tab.findChild(QLabel, "page_label")
            if page_label:
                self.update_page_label(target_tab, row_count)

            # Populate Model
            model = QStandardItemModel(table_view)
            model.setColumnCount(len(columns))
            model.setRowCount(len(results))
            
            # Build headers without metadata initially (will be updated async)
            headers = [str(col) for col in columns]
            pk_indices = []
            if columns and any(x in columns[0].lower() for x in ['id', 'uuid', 'pk']):
                pk_indices.append(0)

            for col_idx, header_text in enumerate(headers):
                model.setHeaderData(col_idx, Qt.Orientation.Horizontal, header_text)

            # Fill Data
            for row_idx, row in enumerate(results):
                pk_val = None
                pk_col_name = None
                if pk_indices:
                    pk_idx = pk_indices[0] 
                    pk_val = row[pk_idx]
                    pk_col_name = columns[pk_idx]

                for col_idx, cell in enumerate(row):
                    item = QStandardItem(str(cell))
                    edit_data = {
                        "pk_col": pk_col_name,
                        "pk_val": pk_val,
                        "orig_val": cell,
                        "col_name": columns[col_idx]
                    }
                    item.setData(edit_data, Qt.ItemDataRole.UserRole)
                    model.setItem(row_idx, col_idx, item)
            
            # Store metadata context on target_tab for async callback
            table_view.setProperty("output_state", output_state)
            
            # Phase 4: Connect signal AFTER all rows inserted (signal batching)
            try: 
                model.itemChanged.disconnect() 
            except: 
                pass
            model.itemChanged.connect(lambda item: self.handle_cell_edit(item, target_tab, table_view))
            
            # Spawn async metadata fetch if table name available
            pending_table_name = output_state.get("real_table_name")
            if pending_table_name and hasattr(self, 'main_window'):
                metadata_signals = MetadataSignals()
                metadata_signals.finished.connect(partial(self.on_metadata_ready, model))
                metadata_signals.error.connect(partial(self.on_metadata_error, target_tab))
                
                worker = FetchMetadataWorker(
                    conn_data,
                    pending_table_name,
                    columns,
                    metadata_signals
                )
                self.main_window.thread_pool.start(worker)

            # Proxy Model (Phase 5: Reuse proxy if exists)
            proxy_model = output_state.get("cached_proxy_model")
            if proxy_model is None:
                # Create proxy once per tab
                proxy_model = QSortFilterProxyModel(table_view)
                proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                proxy_model.setFilterKeyColumn(-1)
                output_state["cached_proxy_model"] = proxy_model
            
            # Reuse proxy by swapping source model
            proxy_model.setSourceModel(model)
            table_view.setModel(proxy_model)
            search_box = target_tab.findChild(QLineEdit, "table_search_box")
            if search_box and search_box.text():
                proxy_model.setFilterFixedString(search_box.text())

            table_view.setProperty("output_state", output_state)
            current_output_index = output_tab_index
            if current_output_index is None:
                current_output_index = resolved_output_index
            self._set_output_tab_title(target_tab, current_output_index, query)
            
            msg = f"Query executed successfully.\n\nTotal rows: {row_count}\nTime: {elapsed_time:.2f} sec"
            status = f"Query executed successfully | Total rows: {row_count} | Time: {elapsed_time:.2f} sec"
            
            if results_info_bar: results_info_bar.show()

        else:
            # --- Non-result-set query (DDL/DML) -> Show Messages Tab (1) ---
            final_tab_index = 1
            
            table_view.setModel(QStandardItemModel(table_view))
            should_refresh_tree = False

            if q_type.startswith("INSERT"):
                msg = f"INSERT 0 {row_count}\n\nQuery returned successfully in {elapsed_time:.2f} sec."
                status = f"INSERT 0 {row_count} | Time: {elapsed_time:.2f} sec"
            elif q_type.startswith("UPDATE"):
                msg = f"UPDATE {row_count}\n\nQuery returned successfully in {elapsed_time:.2f} sec."
                status = f"UPDATE {row_count} | Time: {elapsed_time:.2f} sec"
            elif q_type.startswith("DELETE"):
                msg = f"DELETE {row_count}\n\nQuery returned successfully in {elapsed_time:.2f} sec."
                status = f"DELETE {row_count} | Time: {elapsed_time:.2f} sec"
            elif q_type.startswith("CREATE"):
                msg = f"CREATE TABLE executed successfully.\n\nTime: {elapsed_time:.2f} sec"
                status = f"Table Created | Time: {elapsed_time:.2f} sec"
                should_refresh_tree = True
            elif q_type.startswith("DROP"):
                msg = f"DROP TABLE executed successfully.\n\nTime: {elapsed_time:.2f} sec"
                status = f"DROP success | Time: {elapsed_time:.2f} sec"
                should_refresh_tree = True
            # elif q_type.startswith("ALTER"):
            #     msg = f"ALTER COMMAND executed successfully.\n\nTime: {elapsed_time:.2f} sec"
            #     status = f"ALTER success | Time: {elapsed_time:.2f} sec"
            #     should_refresh_tree = True
            # elif q_type.startswith("TRUNCATE"):
            #     msg = f"TRUNCATE COMMAND executed successfully.\n\nTime: {elapsed_time:.2f} sec"
            #     status = f"TRUNCATE success | Time: {elapsed_time:.2f} sec"
            else:
                msg = f"Query executed successfully.\n\nRows affected: {row_count}\nTime: {elapsed_time:.2f} sec"
                status = f"Rows affected: {row_count} | Time: {elapsed_time:.2f} sec"

            if should_refresh_tree:
                self.main_window.refresh_object_explorer()

            if results_info_bar: results_info_bar.hide()

        if message_view:
            message_view.append(msg)
            sb = message_view.verticalScrollBar()
            sb.setValue(sb.maximum())

        if tab_status_label:
            tab_status_label.setText(status)

        self.status_message_label.setText("Ready")
        
        # --- CRITICAL FIX: Pass the calculated final_tab_index ---
        self.stop_spinner(target_tab, success=True, target_index=final_tab_index) 

        if target_tab in self.running_queries:
            del self.running_queries[target_tab]
        if not self.running_queries:
            self.cancel_action.setEnabled(False)

    def handle_cell_edit(self, item, tab, table_view=None):
        """
        Track changes locally using coordinates (row, col).
        """
        # 1. Retrieve Context Data
        edit_data = item.data(Qt.ItemDataRole.UserRole)
        if not edit_data:
            return 

        orig_val = edit_data.get("orig_val")
        new_val = item.text()

        if table_view is None:
            table_view = self._get_result_table_for_tab(tab)
        if not table_view:
            return
        output_state = table_view.property("output_state") or {}
        modified_coords = output_state.get("modified_coords")
        if modified_coords is None:
            modified_coords = set()
            output_state["modified_coords"] = modified_coords

        # 2. Check if value actually changed
        val_changed = str(orig_val) != str(new_val)
        if str(orig_val) == 'None' and new_val == '': val_changed = False

        row, col = item.row(), item.column()

        if val_changed:
            # Change background to indicate unsaved change
            item.setBackground(QColor("#FFFDD0")) 
            # Store Coordinate (Hashable)
            modified_coords.add((row, col))
            self.status.showMessage("Cell modified")
        else:
            # Revert background
            item.setBackground(QColor(Qt.GlobalColor.white))
            if (row, col) in modified_coords:
                modified_coords.remove((row, col))

        table_view.setProperty("output_state", output_state)

    def on_metadata_ready(self, model, metadata_dict, original_columns, table_name):
        """Callback when metadata finishes fetching asynchronously."""
        try:
            if not model:
                return
            
            # Update headers with metadata (PK indicators, data types)
            pk_indices = []
            headers = []
            
            for idx, col in enumerate(original_columns):
                col_lower = col.lower()
                meta = metadata_dict.get(col_lower, {})
                
                suffix = ""
                if meta.get('pk'):
                    if meta.get('is_serial'):
                        suffix = " [Serial PK]"
                    else:
                        suffix = " [PK]"
                    pk_indices.append(idx)
                elif meta.get('nullable') == False:
                    suffix = " *"
                
                data_type = meta.get('data_type', '')
                compact_type = self._compact_data_type_label(data_type)
                header_text = f"{col}{suffix}\n{compact_type}" if compact_type else f"{col}{suffix}"
                headers.append(header_text)
                model.setHeaderData(idx, Qt.Orientation.Horizontal, header_text)
                if data_type:
                    model.setHeaderData(idx, Qt.Orientation.Horizontal, str(data_type), Qt.ItemDataRole.ToolTipRole)
            
        except Exception as e:
            print(f"Error updating metadata headers: {e}")

    def _compact_data_type_label(self, data_type):
        text = str(data_type or "").strip()
        if not text:
            return ""

        compact = re.sub(r"\s+", " ", text.lower())
        replacements = [
            ("character varying", "varchar"),
            ("varying character", "varchar"),
            ("timestamp without time zone", "timestamp"),
            ("timestamp with time zone", "timestamptz"),
            ("time without time zone", "time"),
            ("time with time zone", "timetz"),
            ("double precision", "float8"),
            ("smallint", "int2"),
            ("int4", "integer"),
            ("bigint", "int8"),
            ("boolean", "bool"),
            ("character", "char"),
        ]

        for source, target in replacements:
            compact = compact.replace(source, target)

        if len(compact) > 20:
            compact = f"{compact[:19]}…"

        return compact

    def on_metadata_error(self, target_tab, error_message):
        """Callback when metadata fetch fails."""
        print(f"Metadata fetch error for {target_tab}: {error_message}")


    def stop_spinner(self, target_tab, success=True, target_index=0):
        if not target_tab: return
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
                        results_info_bar.show()
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

    def load_connection_history(self, target_tab):
        history_list_view = target_tab.findChild(QTreeView, "history_list_view")
        history_details_view = target_tab.findChild(QTextEdit, "history_details_view")
        db_combo_box = target_tab.findChild(QComboBox, "db_combo_box")
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(['Connection History'])
        history_list_view.setModel(model)
        history_details_view.clear()
        history_list_view.expandAll()
        history_list_view.setUniformRowHeights(False)
        history_list_view.setItemsExpandable(False)
        conn_data = db_combo_box.currentData()
        if not conn_data: return
        conn_id = conn_data.get("id")
        try:
            history = db.get_query_history(conn_id)
            for row in history:
                history_id, query, ts, status, rows, duration = row
                clean_query = ' '.join(query.split())
                short_query = clean_query[:90] + ('...' if len(clean_query) > 90 else '')
                dt = datetime.datetime.fromisoformat(ts)
                status_text = (status or "Unknown").upper()
                display_text = f"{short_query}\n{dt.strftime('%Y-%m-%d %H:%M:%S')}  |  {status_text}  |  {duration:.3f}s"
                item = QStandardItem(display_text)
                item.setData({"id": history_id, "query": query, "timestamp": dt.strftime('%Y-%m-%d %H:%M:%S'), "status": status, "rows": rows, "duration": f"{duration:.3f} sec"}, Qt.ItemDataRole.UserRole)
                item.setEditable(False)
                item.setToolTip(query)
                if status_text == "SUCCESS":
                    item.setForeground(QBrush(QColor("#1f7a1f")))
                elif status_text == "FAILURE":
                    item.setForeground(QBrush(QColor("#b42318")))
                model.appendRow(item)

            if model.rowCount() > 0:
                first_index = model.index(0, 0)
                history_list_view.setCurrentIndex(first_index)
                self.display_history_details(first_index, target_tab)
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to load query history:\n{e}")

    def display_history_details(self, index, target_tab):
        history_details_view = target_tab.findChild(QTextEdit, "history_details_view")
        if not index.isValid() or not history_details_view: return
        data = index.model().itemFromIndex(index).data(Qt.ItemDataRole.UserRole)
        details_text = (
            f"Timestamp : {data['timestamp']}\n"
            f"Status    : {data['status']}\n"
            f"Duration  : {data['duration']}\n"
            f"Rows      : {data['rows']}\n\n"
            f"-- Query -----------------------------------------------------------\n"
            f"{data['query']}"
        )
        history_details_view.setPlainText(details_text)

    def _get_selected_history_item(self, target_tab):
        """Helper to get the selected item's data from the history list."""
        history_list_view = target_tab.findChild(QTreeView, "history_list_view")
        selected_indexes = history_list_view.selectionModel().selectedIndexes()
        if not selected_indexes:
            QMessageBox.information(self.main_window, "No Selection", "Please select a history item first.")
            return None
        item = selected_indexes[0].model().itemFromIndex(selected_indexes[0])
        return item.data(Qt.ItemDataRole.UserRole)

    def copy_history_query(self, target_tab):
        history_data = self._get_selected_history_item(target_tab)
        if history_data:
            clipboard = QApplication.clipboard()
            clipboard.setText(history_data['query'])
            self.main_window.status_message_label.setText("Query copied to clipboard.")

    def copy_history_to_editor(self, target_tab):
        history_data = self._get_selected_history_item(target_tab)
        if history_data:
            editor_stack = target_tab.findChild(QStackedWidget, "editor_stack")
            query_editor = target_tab.findChild(QPlainTextEdit, "query_editor")
            if not query_editor:
                QMessageBox.warning(self.main_window, "Editor Not Found", "Could not locate the query editor in this tab.")
                return
            query_editor.setPlainText(history_data['query'])
            
            # Switch back to the query editor view
            if editor_stack:
                editor_stack.setCurrentIndex(0)
            query_view_btn = target_tab.findChild(QPushButton, "query_view_btn")
            history_view_btn = target_tab.findChild(QPushButton, "history_view_btn")
            if query_view_btn: query_view_btn.setChecked(True)
            if history_view_btn: history_view_btn.setChecked(False)
            
            self.main_window.status_message_label.setText("Query copied to editor.")

    def remove_selected_history(self, target_tab):
        history_data = self._get_selected_history_item(target_tab)
        if not history_data: return
        
        history_id = history_data['id']
        reply = QMessageBox.question(self.main_window, "Remove History", "Are you sure you want to remove the selected query history?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.delete_history(history_id)
                self.load_connection_history(target_tab) # Refresh the view
                target_tab.findChild(QTextEdit, "history_details_view").clear()
            except Exception as e:
                QMessageBox.critical(self.main_window, "Error", f"Failed to remove history item:\n{e}")

    def remove_all_history_for_connection(self, target_tab):
        db_combo_box = target_tab.findChild(QComboBox, "db_combo_box")
        conn_data = db_combo_box.currentData()
        if not conn_data:
            QMessageBox.warning(self.main_window, "No Connection", "Please select a connection first.")
            return
        conn_id = conn_data.get("id")
        conn_name = db_combo_box.currentText()
        reply = QMessageBox.question(self.main_window, "Remove All History", f"Are you sure you want to remove all history for the connection:\n'{conn_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.delete_all_history(conn_id)
                self.load_connection_history(target_tab)
            except Exception as e:
                QMessageBox.critical(self.main_window, "Error", f"Failed to clear history for this connection:\n{e}")

      
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
        signals.started.emit(short_id, initial_data)

        self.thread_pool.start(
          RunnableExportFromModel(short_id, model, options, signals)
        )
     
    def _initialize_processes_model(self, tab_content):
        processes_view = tab_content.findChild(QTableView, "processes_view")
        if not processes_view:
            return

        tab_content.process_status_filter = "ALL"

        tab_content.processes_model = QStandardItemModel()
        tab_content.processes_model.setHorizontalHeaderLabels(
           ["PID", "Type", "Status", "Server", "Object", "Time Taken (sec)", "Start Time", "End Time", "Details"]
       )
        processes_view.setModel(tab_content.processes_model)
        # processes_view.resizeColumnsToContents()

            
    def switch_to_processes_view(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
          return

        results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
        header = current_tab.findChild(QWidget, "resultsHeader")
        buttons = header.findChildren(QPushButton)
        results_info_bar = current_tab.findChild(QWidget, "resultsInfoBar")
        process_info_bar = current_tab.findChild(QWidget, "processInfoBar")
        process_filter_bar = current_tab.findChild(QWidget, "processFilterBar")

        if results_stack and len(buttons) >= 4:
          results_stack.setCurrentIndex(3)
          for i, btn in enumerate(buttons[:4]):
            btn.setChecked(i == 3)
          
          # Sync toolbar visibility to match Processes tab
          if results_info_bar:
            results_info_bar.hide()
          if process_filter_bar:
            process_filter_bar.show()
          if process_info_bar:
            process_info_bar.hide()
          
          self.refresh_processes_view()
    
    

    
    def handle_process_started(self, process_id, data):
        # --- START MODIFICATION (Previous change) ---
        target_conn_id = data.get("_conn_id")
        if target_conn_id:
            current_tab = self.tab_widget.currentWidget()
            if current_tab:
                db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
                if db_combo_box:
                    for i in range(db_combo_box.count()):
                        item_data = db_combo_box.itemData(i)
                        if item_data and item_data.get('id') == target_conn_id:
                            # --- Check if index is already selected ---
                            if db_combo_box.currentIndex() != i:
                                db_combo_box.setCurrentIndex(i)
                            else:
                                # If already selected, manually trigger refresh
                                # because currentIndexChanged won't fire
                                self.refresh_processes_view()
                            break
        # --- END MODIFICATION ---

        self.switch_to_processes_view()

        conn = sqlite.connect("databases/hierarchy.db")
        cursor = conn.cursor()
        if target_conn_id:
           cursor.execute("""
            DELETE FROM usf_processes
            WHERE status = 'Running'
              AND server = (
                  SELECT short_name FROM usf_connections WHERE id = ?
               )
          """, (target_conn_id,))

        cursor.execute("""
          INSERT OR REPLACE INTO usf_processes
          (pid, type, status, server, object, time_taken, start_time, end_time, details)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      """, (
          data.get("pid", ""),
          data.get("type", ""),
          "Running",
          data.get("server", ""),
          data.get("object", ""),
          0.0,
          datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
          "",
          data.get("details", "")
      ))
        conn.commit()
        conn.close()

        # refresh_processes_view is now called by the combobox signal
        # OR manually if the combobox was already on the right connection
        if not target_conn_id:
             self.refresh_processes_view()
    # change
    def handle_process_finished(self, process_id, message, time_taken, row_count):
        status = "Successfull" if row_count == 0 else "Successfull"
        conn = sqlite.connect("databases/hierarchy.db")
        cursor = conn.cursor()
        # if "0 rows" in message.lower() or "no data" in message.lower() or "empty" in message.lower():
        #     status = "Warning"
        # else:
        #     status = "Successfull"
        cursor.execute("""
          UPDATE usf_processes
          SET status = ?, time_taken = ?, end_time = ?, details = ?
          WHERE pid = ?
     """, (
           status,
          time_taken,
          datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #   datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
          message,
          process_id
      ))
        conn.commit()
        conn.close()
        self.refresh_processes_view()

    def handle_process_error(self, process_id, error_message):
        conn = sqlite.connect("databases/hierarchy.db")
        cursor = conn.cursor()
        cursor.execute("""
          UPDATE usf_processes
          SET status = ?, end_time = ?, details = ?
          WHERE pid = ?
      """, (
          "Error",
          datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
          error_message,
          process_id
      ))
        conn.commit()
        conn.close()
        self.refresh_processes_view()
    
    
    def refresh_processes_view(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
          return

        db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
        selected_server = None
        if db_combo_box:
          index = db_combo_box.currentIndex()
          if index >= 0:
            data = db_combo_box.itemData(index)
            # --- Use short_name for filtering ---
            selected_server = data.get("short_name") if data else None

        processes_view = current_tab.findChild(QTableView, "processes_view")
        model = getattr(current_tab, "processes_model", None)
        if not processes_view or not model:
          return

        conn = sqlite.connect("databases/hierarchy.db")
        cursor = conn.cursor()

        if selected_server:
          # --- Filter by the selected server (short_name) ---
          cursor.execute("""
            SELECT pid, type, status, server, object, time_taken, start_time, end_time, details
            FROM usf_processes
            WHERE server = ?
            ORDER BY start_time DESC
        """, (selected_server,))
        else:
          # --- If no server selected, show all ---
          cursor.execute("""
            SELECT pid, type, status, server, object, time_taken, start_time, end_time, details
            FROM usf_processes
            ORDER BY start_time DESC
          """)

        data = cursor.fetchall()
        conn.close()

        active_filter = getattr(current_tab, "process_status_filter", "ALL")
        status_counts = {key: 0 for key in self.PROCESS_STATUS_META.keys()}
        filtered_data = []

        for row in data:
            status_key = self._normalize_process_status(row[2])
            if status_key in status_counts:
                status_counts[status_key] += 1

            if active_filter == "ALL" or status_key == active_filter:
                filtered_data.append(row)

        model.clear()
        model.setHorizontalHeaderLabels(
          ["PID", "Type", "Status", "Server", "Object", "Time Taken (sec)", "Start Time", "End Time", "Details"]
        )

        for row_index, row in enumerate(filtered_data):
            items = [QStandardItem(str(col)) for col in row]

            if len(items) > 2:
                items[2].setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            model.appendRow(items)

        self._update_process_summary_ui(current_tab, status_counts, len(data), len(filtered_data))
        
        # --- MODIFICATION: resizeColumnsToContents moved here ---
        processes_view.resizeColumnsToContents()
        processes_view.horizontalHeader().setStretchLastSection(True)
        

    def get_table_column_metadata(self, conn_data, table_name):
      """
        Returns a list of column headers with pgAdmin-style info like:
        emp_id [PK] integer, emp_name character varying(100)
        Uses create_postgres_connection() for consistent DB connection handling.
      """
      headers = []
      conn = None
      try:
        # ✅ Use your reusable connection function
        conn = db.create_postgres_connection(
            host=conn_data["host"],
            port=conn_data["port"],
            database=conn_data["database"],
            user=conn_data["user"],
            password=conn_data["password"]
        )
        if not conn:
            print("Failed to establish connection for metadata fetch.")
            return []

        cur = conn.cursor()
        # NOTE: Using a simple query for metadata. 
        # In worksheet.py, a complex query was used. 
        # I copied the valid logic from there.
        cur.execute("""
            SELECT
                a.attname AS column_name,
                format_type(a.atttypid, a.atttypmod) AS data_type,
                CASE WHEN ct.contype = 'p' THEN '[PK]'
                     WHEN ct.contype = 'f' THEN '[FK]'
                     ELSE ''
                END AS constraint_type
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_constraint ct 
              ON ct.conrelid = c.oid 
             AND a.attnum = ANY(ct.conkey)
            WHERE c.relname = %s 
              AND a.attnum > 0 
              AND NOT a.attisdropped
            ORDER BY a.attnum;
        """, (table_name,))
        rows = cur.fetchall()
        for col, dtype, constraint in rows:
            headers.append(f"{col} {constraint} {dtype}".strip())
      except Exception as e:
        print(f"Metadata fetch error for table '{table_name}': {e}")
      finally:
        if conn:
            conn.close()
      return headers

    def get_current_tab_processes_model(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
            return None, None
        processes_view = current_tab.findChild(QTableView, "processes_view")
        # Ensure we look for the model attribute on the tab, 
        # which should be set during initialization or refresh
        model = getattr(current_tab, "processes_model", None)
        return model, processes_view

    def save_query_to_history(self, conn_data, query, status, rows, duration):
        conn_id = conn_data.get("id")
        if not conn_id: return
        try:
            db.save_query_history(conn_id, query, status, rows, duration)
        except Exception as e:
            self.status.showMessage(f"Could not save query to history: {e}", 4000)

    def open_limit_offset_dialog(self, tab_content):
        """Opens a dialog to set Limit and Offset like pgAdmin."""
        dialog = QDialog(self.main_window)
        dialog.setWindowTitle("Query Options")
        dialog.setFixedSize(300, 150)
        
        layout = QFormLayout(dialog)

        # Limit Input
        limit_spin = QSpinBox()
        limit_spin.setRange(0, 999999999) # 0 means no limit (logic handled below)
        limit_spin.setValue(int(getattr(tab_content, 'current_limit', 0) or 0))
        limit_spin.setSpecialValueText("No Limit") # If value is 0
        layout.addRow("Rows Limit:", limit_spin)

        # Offset Input
        offset_spin = QSpinBox()
        offset_spin.setRange(0, 999999999)
        offset_spin.setValue(getattr(tab_content, 'current_offset', 0))
        layout.addRow("Start Row (Offset):", offset_spin)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

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

            # Execute Query with new settings
            # Call WorksheetManager to execute
            self.main_window.worksheet_manager.execute_query(preserve_pagination=True)

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
        """
        Creates the Results UI container (Header, Stack, Footer).
        Returns the container QWidget.
        """
        results_container = QWidget()
        results_container.setMinimumHeight(30)
        results_layout = QVBoxLayout(results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(0)

        # ---------------------------------------------------------
        # 1. Results Header (Buttons Only)
        # ---------------------------------------------------------
        results_header = QWidget()
        results_header.setObjectName("resultsHeader")
        results_header_layout = QHBoxLayout(results_header)
        results_header_layout.setContentsMargins(6, 3, 6, 1)
        results_header_layout.setSpacing(4)

        output_btn = QPushButton("Output")
        message_btn = QPushButton("Messages")
        notification_btn = QPushButton("Notifications")
        process_btn = QPushButton("Processes")

        output_btn.setMinimumWidth(100)
        message_btn.setMinimumWidth(100)
        notification_btn.setMinimumWidth(120)
        process_btn.setMinimumWidth(100)

        output_btn.setCheckable(True)
        message_btn.setCheckable(True)
        notification_btn.setCheckable(True)
        process_btn.setCheckable(True)
        output_btn.setChecked(True)

        explain_btn = QPushButton("Explain")
        explain_btn.setMinimumWidth(100)
        explain_btn.setCheckable(True)

        results_header_layout.addWidget(output_btn)
        results_header_layout.addWidget(message_btn)
        results_header_layout.addWidget(notification_btn)
        results_header_layout.addWidget(process_btn)
        results_header_layout.addWidget(explain_btn)
        results_header_layout.addStretch()
        
        results_layout.addWidget(results_header)

        # ---------------------------------------------------------
        # 2. Results Info Bar (Showing Rows & Pagination) - BELOW Buttons
        # ---------------------------------------------------------
        results_info_bar = QWidget()
        results_info_bar.setObjectName("resultsInfoBar")
        results_info_bar.setStyleSheet(
            "QWidget#resultsInfoBar { "
            "background-color: #ECEFF3; "
            "border-top: 1px solid #C9CFD8; "
            "border-bottom: 1px solid #C9CFD8; "
            "}"
        )
        results_info_layout = QHBoxLayout(results_info_bar)
        results_info_layout.setContentsMargins(6, 3, 6, 3)
        results_info_layout.setSpacing(6)

        
        # --- Button Style for Bottom Bar (Reuse btn_style) ---
        btn_style_bottom = (
            "QPushButton, QToolButton { "
            "padding: 2px 8px; border: 1px solid #b9b9b9; "
            "background-color: #ffffff; border-radius: 4px; "
            "font-size: 9pt; color: #333333; "
            "} "
            "QPushButton:hover, QToolButton:hover { "
            "background-color: #e8e8e8; border-color: #9c9c9c; "
            "} "
            "QPushButton:pressed, QToolButton:pressed { "
            "background-color: #dcdcdc; "
            "} "
        )

        add_row_btn = QPushButton()
        add_row_btn.setIcon(QIcon("assets/row-plus.svg"))
        add_row_btn.setIconSize(QSize(16, 16))
        add_row_btn.setFixedSize(30, 30)
        add_row_btn.setToolTip("Add new row")
        add_row_btn.setStyleSheet(btn_style_bottom)
        add_row_btn.clicked.connect(self.add_empty_row)

        save_row_btn = QPushButton()
        save_row_btn.setIcon(QIcon("assets/save.svg"))
        save_row_btn.setIconSize(QSize(16, 16))
        save_row_btn.setFixedSize(30, 30)
        save_row_btn.setToolTip("Save new row")
        save_row_btn.setStyleSheet(btn_style_bottom)
        results_info_layout.addWidget(add_row_btn)
        results_info_layout.addWidget(save_row_btn)
        
        save_row_btn.clicked.connect(self.save_new_row)

        # --- COPY / PASTE BUTTONS (pgAdmin style) ---
        copy_btn = QToolButton()
        copy_btn.setIcon(QIcon("assets/copy.svg")) 
        copy_btn.setIconSize(QSize(19, 19))
        copy_btn.setFixedSize(30, 30)
        copy_btn.setToolTip("Copy selected cells (Ctrl+C)")
        copy_btn.setStyleSheet(btn_style_bottom)
        # Logic connected later when table is created

        # Copy connects after table creation

        paste_btn = QToolButton()
        paste_btn.setIcon(QIcon("assets/paste.svg")) 
        paste_btn.setIconSize(QSize(19, 19))
        paste_btn.setFixedSize(30, 30)
        paste_btn.setToolTip("Paste to editor")
        paste_btn.setStyleSheet(btn_style_bottom)
        paste_btn.clicked.connect(self.paste_to_editor)

        # --- New: Delete Row Button 
        delete_row_btn = QPushButton()
        delete_row_btn.setIcon(QIcon("assets/trash.svg")) 
        delete_row_btn.setIconSize(QSize(16, 16))
        delete_row_btn.setFixedSize(30, 30)
        delete_row_btn.setToolTip("Delete selected row(s)")
        delete_row_btn.setObjectName("delete_row_btn") 
        delete_row_btn.setStyleSheet(btn_style_bottom) 

        delete_row_btn.clicked.connect(self.delete_selected_row) 

        results_info_layout.addWidget(delete_row_btn)
        results_info_layout.addWidget(copy_btn)
        results_info_layout.addWidget(paste_btn)

        download_btn = QPushButton()
        download_btn.setIcon(QIcon("assets/export.svg"))
        download_btn.setIconSize(QSize(16, 16))
        download_btn.setFixedSize(30, 30)
        download_btn.setToolTip("Download query result")
        download_btn.setStyleSheet(btn_style_bottom)
        download_btn.clicked.connect(lambda: self.download_result(tab_content))
        results_info_layout.addWidget(download_btn)

        search_box = QLineEdit()
        search_box.setPlaceholderText("Search...")
        icon_path = "assets/search.svg" 
        
        if os.path.exists(icon_path):
            search_icon = QIcon(icon_path)
            search_box.addAction(search_icon, QLineEdit.ActionPosition.LeadingPosition)
        search_box.setFixedHeight(28)
        search_box.setFixedWidth(180)
        search_box.setObjectName("table_search_box")
        search_box.hide()  # Initially Hidden
        search_box.installEventFilter(self)
        
        # Search Button (Compact/Small)
        table_search_btn = QToolButton()
        table_search_btn.setObjectName("table_search_btn")
        table_search_btn.setIcon(QIcon(icon_path if os.path.exists(icon_path) else ""))
        table_search_btn.setFixedSize(30, 30)
        table_search_btn.setToolTip("Search in Results")
        table_search_btn.setStyleSheet("""
            QToolButton {
                border: 1px solid #b9b9b9;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QToolButton:hover {
                background-color: #e8e8e8;
                border: 1px solid #9c9c9c;
            }
        """)
        table_search_btn.clicked.connect(self.toggle_table_search)
        
        # Create debouncer timer for search (Phase 2 optimization)
        search_debounce_timer = QTimer()
        search_debounce_timer.setInterval(300)  # 300ms debounce delay
        search_debounce_timer.setSingleShot(True)
        
        def trigger_filter():
            current_table = self._get_result_table_for_tab(tab_content)
            if current_table:
                current_model = current_table.model()
                if isinstance(current_model, QSortFilterProxyModel):
                    current_model.setFilterFixedString(search_box.text())
        
        def on_search_text_changed(text):
            # Reset timer every keystroke (debounce)
            search_debounce_timer.stop()
            search_debounce_timer.start()
        
        search_debounce_timer.timeout.connect(trigger_filter)
        search_box.textChanged.connect(on_search_text_changed)
        results_info_layout.addWidget(search_box)
        results_info_layout.addWidget(table_search_btn)

        results_info_layout.addStretch()
    
        # Info Label (e.g., "Showing rows 1 - 1000")
        rows_info_label = QLabel("Showing Rows")
        rows_info_label.setObjectName("rows_info_label")
        font = QFont()
        font.setBold(True)
        rows_info_label.setFont(font)
        results_info_layout.addWidget(rows_info_label)

        # Edit Button (Pencil Icon)
        rows_setting_btn = QToolButton()
        rows_setting_btn.setIcon(QIcon("assets/list-details.svg"))
        rows_setting_btn.setIconSize(QSize(16, 16))
        rows_setting_btn.setFixedSize(28, 28)
        rows_setting_btn.setToolTip("Edit Limit/Offset")
        rows_setting_btn.setStyleSheet(btn_style_bottom)
        rows_setting_btn.clicked.connect(lambda: self.open_limit_offset_dialog(tab_content))
        results_info_layout.addWidget(rows_setting_btn)

        # ===== PAGINATION UI =====
        arrow_font = QFont("Segoe UI", 16, QFont.Weight.Bold) # Restored for visibility
        
        nav_btn_style = ("QPushButton { "
                         "border: 1px solid #b9b9b9; "
                         "border-radius: 4px; "
                         "background-color: #ffffff; "
                         "color: #333333; "
                         "padding: 0px; " # Center icon/text
                         "} "
                         "QPushButton:hover { "
                         "background-color: #e8e8e8; "
                         "border-color: #9c9c9c; "
                         "} "
                         "QPushButton:pressed { "
                         "background-color: #dcdcdc; "
                         "} "
                         "QPushButton:disabled { "
                         "background-color: #f2f2f2; "
                         "color: #aaaaaa; "
                         "border-color: #cfcfcf; "
                         "}")

        # Prev button
        prev_btn = QPushButton("◀")
        prev_btn.setFixedSize(30, 28)
        prev_btn.setFont(arrow_font)
        prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        prev_btn.setEnabled(True) # Initially disabled
        prev_btn.setObjectName("prev_btn")
        prev_btn.setStyleSheet(nav_btn_style)

        # Page label
        page_label = QLabel("Page 1")
        page_label.setMinimumWidth(60)
        page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_label.setFont(QFont("Segoe UI", 9))
        page_label.setObjectName("page_label")

        # Next button
        next_btn = QPushButton("▶")
        next_btn.setFixedSize(30, 28)
        next_btn.setFont(arrow_font)
        next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        next_btn.setEnabled(True) # Initially disabled until results load
        next_btn.setObjectName("next_btn")
        next_btn.setStyleSheet(nav_btn_style)

        results_info_layout.addWidget(prev_btn)
        results_info_layout.addWidget(page_label)
        results_info_layout.addWidget(next_btn)
        
        results_layout.addWidget(results_info_bar)

        # ----- PROCESS FILTER BAR (Toolbar-like) -----
        process_filter_bar = QWidget()
        process_filter_bar.setObjectName("processFilterBar")
        process_filter_layout = QHBoxLayout(process_filter_bar)
        process_filter_layout.setContentsMargins(6, 3, 6, 3)
        process_filter_layout.setSpacing(6)

        filter_btn_style = """
            QPushButton {
                border: 1px solid #B8BEC6;
                border-radius: 4px;
                background: #F9FAFB;
                color: #1f2937;
                padding: 4px 10px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background: #E7EBF1;
                border-color: #9FA6AF;
            }
            QPushButton:pressed {
                background: #D9DFE8;
            }
            QPushButton:checked {
                background: #8E959E;
                border-color: #7A828C;
                color: #ffffff;
                font-weight: 600;
            }
        """

        all_filter_btn = QPushButton("All (0)")
        running_filter_btn = QPushButton("Running (0)")
        success_filter_btn = QPushButton("Successfull (0)")
        warning_filter_btn = QPushButton("Warning (0)")
        error_filter_btn = QPushButton("Error (0)")

        for btn in [all_filter_btn, running_filter_btn, success_filter_btn, warning_filter_btn, error_filter_btn]:
            btn.setCheckable(True)
            btn.setStyleSheet(filter_btn_style)
            btn.setFixedHeight(28)
            btn.setMinimumWidth(84)
            process_filter_layout.addWidget(btn)

        process_filter_group = QButtonGroup(process_filter_bar)
        process_filter_group.setExclusive(True)
        process_filter_group.addButton(all_filter_btn)
        process_filter_group.addButton(running_filter_btn)
        process_filter_group.addButton(success_filter_btn)
        process_filter_group.addButton(warning_filter_btn)
        process_filter_group.addButton(error_filter_btn)
        all_filter_btn.setChecked(True)

        all_filter_btn.clicked.connect(lambda: self._set_process_filter(tab_content, "ALL"))
        running_filter_btn.clicked.connect(lambda: self._set_process_filter(tab_content, "RUNNING"))
        success_filter_btn.clicked.connect(lambda: self._set_process_filter(tab_content, "SUCCESSFULL"))
        warning_filter_btn.clicked.connect(lambda: self._set_process_filter(tab_content, "WARNING"))
        error_filter_btn.clicked.connect(lambda: self._set_process_filter(tab_content, "ERROR"))

        tab_content.process_filter_buttons = {
            "ALL": all_filter_btn,
            "RUNNING": running_filter_btn,
            "SUCCESSFULL": success_filter_btn,
            "WARNING": warning_filter_btn,
            "ERROR": error_filter_btn,
        }

        process_filter_layout.addStretch()

        refresh_now_btn = QPushButton("Refresh")
        refresh_now_btn.setObjectName("process_refresh_now_btn")
        refresh_now_btn.setStyleSheet(filter_btn_style)
        refresh_now_btn.setFixedHeight(28)
        refresh_now_btn.setMinimumWidth(76)
        refresh_now_btn.clicked.connect(self.refresh_processes_view)
        process_filter_layout.addWidget(refresh_now_btn)

        process_filter_bar.setStyleSheet("background: #ECEFF3; border-bottom: 1px solid #C9CFD8;")
        process_filter_bar.hide()
        results_layout.addWidget(process_filter_bar)

        # ----- PROCESS INFO BAR (Hidden - Summary shown in status bar) -----
        process_info_bar = QWidget()
        process_info_bar.setObjectName("processInfoBar")
        process_info_layout = QHBoxLayout(process_info_bar)
        process_info_layout.setContentsMargins(8, 3, 8, 3)
        process_info_layout.setSpacing(20)

        # Hidden labels (kept for compatibility)
        process_summary_label = QLabel("")
        process_summary_label.setObjectName("process_summary_label")
        process_selection_label = QLabel("")
        process_selection_label.setObjectName("process_selection_label")
        
        process_info_bar.setStyleSheet("background: transparent; border: none;")
        process_info_bar.hide()
        results_layout.addWidget(process_info_bar)
        
        # Store references for later access
        tab_content.process_filter_bar = process_filter_bar

        # --- Pagination Logic ---
        def update_page_ui(tab):
            page_label.setText(f"Page {tab.current_page}")
            
            # Prev
            prev_btn.setEnabled(tab.current_page > 1)
            
            limit = getattr(tab, 'current_limit', 0)
            offset = getattr(tab, 'current_offset', 0)
            
            if limit and limit > 0:
                rows_info_label.setText(f"Limit: {limit} | Offset: {offset}")
            else:
                rows_info_label.setText("No Limit") # No limit set

        
        def go_prev():
            tab = tab_content
            if not tab or tab.current_page <= 1:
                return
            tab.current_page -= 1
            tab.current_offset = (tab.current_page - 1) * tab.current_limit
            update_page_ui(tab)
            self.main_window.worksheet_manager.execute_query(preserve_pagination=True)

        def go_next():
            tab = tab_content
            if not tab.has_more_pages:
                return
            tab.current_page += 1
            tab.current_offset = (tab.current_page - 1) * tab.current_limit
            update_page_ui(tab)
            self.main_window.worksheet_manager.execute_query(preserve_pagination=True)

        prev_btn.clicked.connect(go_prev)
        next_btn.clicked.connect(go_next)

        # ---------------------------------------------------------

        results_button_group = QButtonGroup(results_container) # Parent to container
        results_button_group.setExclusive(True)
        results_button_group.addButton(output_btn, 0)
        results_button_group.addButton(message_btn, 1)
        results_button_group.addButton(notification_btn, 2)
        results_button_group.addButton(process_btn, 3)
        results_button_group.addButton(explain_btn, 5)

        results_stack = QStackedWidget()
        results_stack.setObjectName("results_stacked_widget")

        # Page 0: Output Tabs (multiple result tables)
        output_tabs = QTabWidget()
        output_tabs.setObjectName("output_tabs")
        output_tabs.setTabsClosable(True)
        output_tabs.setMovable(False)
        output_tabs.setTabBarAutoHide(False)
        output_tabs.setDocumentMode(True)
        output_tabs.tabCloseRequested.connect(lambda index: self._handle_output_tab_close(tab_content, index))
        results_stack.addWidget(output_tabs)

        copy_btn.clicked.connect(self.copy_current_result_table)

        # Page 1: Message View
        message_view = QTextEdit()
        message_view.setObjectName("message_view")
        message_view.setReadOnly(True)
        results_stack.addWidget(message_view)

        # Page 2: Notification View
        notification_view = QLabel("Notifications will appear here.")
        notification_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        results_stack.addWidget(notification_view)

        # Page 3: Processes View
        processes_view = QTableView()
        processes_view.setObjectName("processes_view")
        processes_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        processes_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        processes_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        processes_view.setAlternatingRowColors(True)
        processes_view.horizontalHeader().setSectionsClickable(True)
        processes_view.verticalHeader().setSectionsClickable(True)
        processes_view.verticalHeader().setDefaultSectionSize(28)
        processes_view.horizontalHeader().setStretchLastSection(True)
        processes_view.setItemDelegate(ProcessRowDelegate(self.PROCESS_STATUS_META, parent=processes_view))
        processes_view.clicked.connect(lambda idx: self._handle_process_cell_click(tab_content, idx))
        processes_view.horizontalHeader().sectionClicked.connect(
            lambda section: self._handle_process_column_header_click(tab_content, section)
        )
        processes_view.verticalHeader().sectionClicked.connect(
            lambda section: self._handle_process_row_header_click(tab_content, section)
        )
        
        # Initialize the processes model before adding to stack
        self._initialize_processes_model(tab_content)
        
        results_stack.addWidget(processes_view)
        
        # Page 4: Spinner / Loading
        spinner_overlay_widget = QWidget()
        spinner_layout = QHBoxLayout(spinner_overlay_widget)
        spinner_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinner_movie = QMovie("assets/spinner.gif")
        spinner_label = QLabel()
        spinner_label.setObjectName("spinner_label")

        if not spinner_movie.isValid():
            spinner_label.setText("Loading...")
        else:
            spinner_label.setMovie(spinner_movie)
            spinner_movie.setScaledSize(QSize(32, 32))
            
        loading_text_label = QLabel("Waiting for query to complete...")
        font = QFont()
        font.setPointSize(10)
        loading_text_label.setFont(font)
        loading_text_label.setStyleSheet("color: #555;")
        spinner_layout.addWidget(spinner_label)
        spinner_layout.addWidget(loading_text_label)
        results_stack.addWidget(spinner_overlay_widget)

        explain_visualizer = ExplainVisualizer()
        results_stack.addWidget(explain_visualizer)      # Index 5

        results_layout.addWidget(results_stack)
        results_layout.setStretchFactor(results_stack, 1)

        tab_status_label = QLabel("Ready")
        tab_status_label.setObjectName("tab_status_label")
        results_layout.addWidget(tab_status_label)
        results_layout.setStretchFactor(tab_status_label, 0)

        def switch_results_view(index):
            results_stack.setCurrentIndex(index)

            if index == 0:
                results_info_bar.show()
                process_info_bar.hide()
                process_filter_bar.hide()
            elif index == 3:
                results_info_bar.hide()
                process_filter_bar.show()
                process_info_bar.hide()
                self.refresh_processes_view()
            else:
                results_info_bar.hide()
                process_info_bar.hide()
                process_filter_bar.hide()
           
        output_btn.clicked.connect(lambda: switch_results_view(0))
        message_btn.clicked.connect(lambda: switch_results_view(1))
        notification_btn.clicked.connect(lambda: switch_results_view(2))
        process_btn.clicked.connect(lambda: switch_results_view(3))
        explain_btn.clicked.connect(lambda: switch_results_view(5))
        
        return results_container