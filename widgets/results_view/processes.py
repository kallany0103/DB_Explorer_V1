import datetime
import sqlite3 as sqlite

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPalette, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QComboBox, QPushButton, QStackedWidget, QStyledItemDelegate, QStyle, QStyleOptionViewItem, QTableView, QWidget, QAbstractItemView


class ProcessRowDelegate(QStyledItemDelegate):
    """Draws status-based row background while preserving distinct cell/row/column selection behavior."""

    def __init__(self, status_meta, default_bg="#ffffff", parent=None):
        super().__init__(parent)
        self.status_meta = status_meta or {}
        self.default_bg = QColor(default_bg)
        self._status_column_cache = {}

    def _get_status_column(self, model):
        if not model or not hasattr(model, "columnCount"):
            return -1

        model_id = id(model)
        if model_id in self._status_column_cache:
            return self._status_column_cache[model_id]

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

        if is_item_selected:
            paint_option.palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        else:
            paint_option.palette.setColor(QPalette.ColorRole.Text, QColor("#1f2937"))

        super().paint(painter, paint_option, index)
        painter.restore()


def create_processes_view(manager, tab_content):
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
    processes_view.setItemDelegate(ProcessRowDelegate(manager.PROCESS_STATUS_META, parent=processes_view))
    processes_view.clicked.connect(lambda idx: manager._handle_process_cell_click(tab_content, idx))
    processes_view.horizontalHeader().sectionClicked.connect(
        lambda section: manager._handle_process_column_header_click(tab_content, section)
    )
    processes_view.verticalHeader().sectionClicked.connect(
        lambda section: manager._handle_process_row_header_click(tab_content, section)
    )
    return processes_view


def get_process_status_meta(manager, status_text):
    status_key = manager._normalize_process_status(status_text)
    return manager.PROCESS_STATUS_META.get(status_key, manager.DEFAULT_PROCESS_STATUS_META)


def _request_processes_refresh(manager, delay_ms=None):
    requested_delay = delay_ms
    if requested_delay is None:
        requested_delay = int(getattr(manager, "process_refresh_debounce_ms", 50) or 50)

    refresh_timer = getattr(manager, "_process_refresh_timer", None)
    if refresh_timer is None:
        refresh_timer = QTimer(manager)
        refresh_timer.setSingleShot(True)
        refresh_timer.timeout.connect(manager.refresh_processes_view)
        manager._process_refresh_timer = refresh_timer

    refresh_timer.stop()
    refresh_timer.start(max(0, int(requested_delay)))


def set_process_filter(manager, tab_content, filter_key):
    tab_content.process_status_filter = filter_key
    manager.refresh_processes_view()


def update_process_summary_ui(manager, target_tab, status_counts, total_count, visible_count):
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


def handle_process_cell_click(manager, tab_content, index):
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
    _message = f"{selection_mode} selected: R{index.row() + 1}, C{index.column() + 1} ({column_name})"


def handle_process_column_header_click(manager, tab_content, column):
    processes_view = tab_content.findChild(QTableView, "processes_view")
    if not processes_view:
        return

    processes_view.selectColumn(column)


def handle_process_row_header_click(manager, tab_content, row):
    processes_view = tab_content.findChild(QTableView, "processes_view")
    if not processes_view:
        return

    processes_view.selectRow(row)


def initialize_processes_model(manager, tab_content):
    processes_view = tab_content.findChild(QTableView, "processes_view")
    if not processes_view:
        return

    tab_content.process_status_filter = "ALL"

    tab_content.processes_model = QStandardItemModel()
    tab_content.processes_model.setHorizontalHeaderLabels(
        ["PID", "Type", "Status", "Server", "Object", "Time Taken (sec)", "Start Time", "End Time", "Details"]
    )
    processes_view.setModel(tab_content.processes_model)


def switch_to_processes_view(manager):
    current_tab = manager.tab_widget.currentWidget()
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

        if results_info_bar:
            results_info_bar.hide()
        if process_filter_bar:
            process_filter_bar.show()
        if process_info_bar:
            process_info_bar.hide()

        manager.refresh_processes_view()


def handle_process_started(manager, process_id, data):
    target_conn_id = data.get("_conn_id")
    if target_conn_id:
        current_tab = manager.tab_widget.currentWidget()
        if current_tab:
            db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
            if db_combo_box:
                for i in range(db_combo_box.count()):
                    item_data = db_combo_box.itemData(i)
                    if item_data and item_data.get("id") == target_conn_id:
                        if db_combo_box.currentIndex() != i:
                            db_combo_box.setCurrentIndex(i)
                        break

    manager.switch_to_processes_view()

    conn = sqlite.connect("databases/hierarchy.db")
    cursor = conn.cursor()
    if target_conn_id:
        cursor.execute(
            """
            DELETE FROM usf_processes
            WHERE status = 'Running'
              AND server = (
                  SELECT short_name FROM usf_connections WHERE id = ?
               )
            """,
            (target_conn_id,),
        )

    cursor.execute(
        """
        INSERT OR REPLACE INTO usf_processes
        (pid, type, status, server, object, time_taken, start_time, end_time, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("pid", ""),
            data.get("type", ""),
            "Running",
            data.get("server", ""),
            data.get("object", ""),
            0.0,
            datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
            "",
            data.get("details", ""),
        ),
    )
    conn.commit()
    conn.close()

    _request_processes_refresh(manager)


def handle_process_finished(manager, process_id, message, time_taken, row_count):
    status = "Successfull" if row_count == 0 else "Successfull"
    conn = sqlite.connect("databases/hierarchy.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE usf_processes
        SET status = ?, time_taken = ?, end_time = ?, details = ?
        WHERE pid = ?
        """,
        (
            status,
            time_taken,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            message,
            process_id,
        ),
    )
    conn.commit()
    conn.close()
    _request_processes_refresh(manager)


def handle_process_error(manager, process_id, error_message):
    conn = sqlite.connect("databases/hierarchy.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE usf_processes
        SET status = ?, end_time = ?, details = ?
        WHERE pid = ?
        """,
        (
            "Error",
            datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
            error_message,
            process_id,
        ),
    )
    conn.commit()
    conn.close()
    _request_processes_refresh(manager)


def refresh_processes_view(manager):
    current_tab = manager.tab_widget.currentWidget()
    if not current_tab:
        return

    db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
    selected_server = None
    if db_combo_box:
        index = db_combo_box.currentIndex()
        if index >= 0:
            data = db_combo_box.itemData(index)
            selected_server = data.get("short_name") if data else None

    processes_view = current_tab.findChild(QTableView, "processes_view")
    model = getattr(current_tab, "processes_model", None)
    if not processes_view or not model:
        return

    conn = sqlite.connect("databases/hierarchy.db")
    cursor = conn.cursor()

    if selected_server:
        cursor.execute(
            """
            SELECT pid, type, status, server, object, time_taken, start_time, end_time, details
            FROM usf_processes
            WHERE server = ?
            ORDER BY start_time DESC
            """,
            (selected_server,),
        )
    else:
        cursor.execute(
            """
            SELECT pid, type, status, server, object, time_taken, start_time, end_time, details
            FROM usf_processes
            ORDER BY start_time DESC
            """
        )

    data = cursor.fetchall()
    conn.close()

    active_filter = getattr(current_tab, "process_status_filter", "ALL")
    status_counts = {key: 0 for key in manager.PROCESS_STATUS_META.keys()}
    filtered_data = []

    for row in data:
        status_key = manager._normalize_process_status(row[2])
        if status_key in status_counts:
            status_counts[status_key] += 1

        if active_filter == "ALL" or status_key == active_filter:
            filtered_data.append(row)

    model.clear()
    model.setHorizontalHeaderLabels(
        ["PID", "Type", "Status", "Server", "Object", "Time Taken (sec)", "Start Time", "End Time", "Details"]
    )

    for _, row in enumerate(filtered_data):
        items = [QStandardItem(str(col)) for col in row]
        for item in items:
            item.setEditable(False)

        if len(items) > 2:
            items[2].setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        model.appendRow(items)

    manager._update_process_summary_ui(current_tab, status_counts, len(data), len(filtered_data))
    processes_view.resizeColumnsToContents()
    processes_view.horizontalHeader().setStretchLastSection(True)


def get_current_tab_processes_model(manager):
    current_tab = manager.tab_widget.currentWidget()
    if not current_tab:
        return None, None
    processes_view = current_tab.findChild(QTableView, "processes_view")
    model = getattr(current_tab, "processes_model", None)
    return model, processes_view
