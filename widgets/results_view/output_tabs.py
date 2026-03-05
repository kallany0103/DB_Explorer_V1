from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QLineEdit,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)


def _stop_chunk_loader_for_table(table_view):
    if not table_view:
        return
    output_state = table_view.property("output_state") or {}
    timer = output_state.get("chunk_loader")
    if timer:
        try:
            timer.stop()
            timer.deleteLater()
        except Exception:
            pass
    output_state["chunk_loader"] = None
    table_view.setProperty("output_state", output_state)


def _stop_chunk_loader_for_container(output_container):
    if not output_container:
        return
    table_view = output_container.findChild(QTableView, "results_table")
    _stop_chunk_loader_for_table(table_view)


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


def create_output_tabs_view(manager, tab_content):
    output_tabs = QTabWidget()
    output_tabs.setObjectName("output_tabs")
    output_tabs.setTabsClosable(True)
    output_tabs.setMovable(False)
    output_tabs.setTabBarAutoHide(False)
    output_tabs.setDocumentMode(True)
    output_tabs.tabCloseRequested.connect(lambda index: manager._handle_output_tab_close(tab_content, index))
    return output_tabs


def get_output_tabs_widget(manager, tab_content):
    if not tab_content:
        return None
    return tab_content.findChild(QTabWidget, "output_tabs")


def ensure_output_tabs_widget(manager, tab_content):
    output_tabs = get_output_tabs_widget(manager, tab_content)
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
    output_tabs.tabCloseRequested.connect(lambda index: manager._handle_output_tab_close(tab_content, index))

    output_container = QWidget()
    output_layout = QVBoxLayout(output_container)
    output_layout.setContentsMargins(0, 0, 0, 0)
    output_layout.setSpacing(0)

    existing_table = old_page_zero.findChild(QTableView, "results_table") if old_page_zero else None
    if existing_table:
        existing_table.setParent(None)
        output_layout.addWidget(existing_table)
    else:
        output_layout.addWidget(create_output_table_view(manager, tab_content))

    output_tabs.addTab(output_container, "Result 1")
    output_tabs.setCurrentIndex(0)

    results_stack.insertWidget(0, output_tabs)
    if old_page_zero is not None:
        results_stack.removeWidget(old_page_zero)
        old_page_zero.deleteLater()

    return output_tabs


def get_output_tab_container(manager, tab_content, output_tab_index=None):
    output_tabs = ensure_output_tabs_widget(manager, tab_content)
    if not output_tabs:
        return None
    if output_tab_index is not None and 0 <= output_tab_index < output_tabs.count():
        return output_tabs.widget(output_tab_index)
    return output_tabs.currentWidget()


def get_result_table_for_tab(manager, tab_content, output_tab_index=None):
    output_container = get_output_tab_container(manager, tab_content, output_tab_index)
    if not output_container:
        return None
    return output_container.findChild(QTableView, "results_table")


def ensure_result_table_for_tab(manager, tab_content, output_tab_index=None):
    output_tabs = ensure_output_tabs_widget(manager, tab_content)
    if not output_tabs:
        return None, None

    ensure_at_least_one_output_tab(manager, tab_content)

    if output_tab_index is not None and 0 <= output_tab_index < output_tabs.count():
        output_tabs.setCurrentIndex(output_tab_index)

    output_container = output_tabs.currentWidget()
    if not output_container:
        ensure_at_least_one_output_tab(manager, tab_content)
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
        table_view = create_output_table_view(manager, tab_content)
        output_layout.addWidget(table_view)

    return table_view, output_tabs.currentIndex()


def create_output_table_view(manager, tab_content):
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
    table_view.customContextMenuRequested.connect(manager.show_results_context_menu)
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


def create_output_tab(manager, tab_content, title=None, activate=True):
    output_tabs = ensure_output_tabs_widget(manager, tab_content)
    if not output_tabs:
        return None

    output_container = QWidget()
    output_layout = QVBoxLayout(output_container)
    output_layout.setContentsMargins(0, 0, 0, 0)
    output_layout.setSpacing(0)

    table_view = create_output_table_view(manager, tab_content)
    output_layout.addWidget(table_view)

    default_title = title or f"Result {output_tabs.count() + 1}"
    new_index = output_tabs.addTab(output_container, default_title)
    if activate:
        output_tabs.setCurrentIndex(new_index)
    return new_index


def add_output_tab_with_table_name(manager, tab_content, query=None, table_name=None, activate=True):
    output_tabs = ensure_output_tabs_widget(manager, tab_content)
    if not output_tabs:
        return None

    resolved_table_name = table_name
    if not resolved_table_name and query:
        resolved_table_name = manager._extract_query_table_name(query)

    if resolved_table_name:
        title = f"{resolved_table_name} {output_tabs.count() + 1}"
    else:
        title = f"Result {output_tabs.count() + 1}"

    return create_output_tab(manager, tab_content, title=title, activate=activate)


def ensure_at_least_one_output_tab(manager, tab_content):
    output_tabs = ensure_output_tabs_widget(manager, tab_content)
    if output_tabs and output_tabs.count() == 0:
        output_container = QWidget()
        output_layout = QVBoxLayout(output_container)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(0)
        table_view = create_output_table_view(manager, tab_content)
        output_layout.addWidget(table_view)
        output_tabs.addTab(output_container, "Result 1")
        output_tabs.setCurrentIndex(0)


def set_output_tab_title(manager, tab_content, output_tab_index, query):
    output_tabs = ensure_output_tabs_widget(manager, tab_content)
    if not output_tabs or output_tab_index is None:
        return
    if output_tab_index < 0 or output_tab_index >= output_tabs.count():
        return

    table_name = manager._extract_query_table_name(query)
    if not table_name:
        table_name = "Result"

    display_number = output_tab_index + 1
    output_tabs.setTabText(output_tab_index, f"{table_name} {display_number}")


def handle_output_tab_close(manager, tab_content, index):
    output_tabs = ensure_output_tabs_widget(manager, tab_content)
    if not output_tabs:
        return
    if output_tabs.count() <= 1:
        return
    output_container = output_tabs.widget(index)
    _stop_chunk_loader_for_container(output_container)
    output_tabs.removeTab(index)
    if output_tabs.count() == 0:
        create_output_tab(manager, tab_content, title="Result 1", activate=True)


def serialize_output_tabs(manager, tab_content):
    output_tabs = ensure_output_tabs_widget(manager, tab_content)
    if not output_tabs:
        return {"tabs": ["Result 1"], "active_index": 0}

    tab_titles = [output_tabs.tabText(i) or f"Result {i + 1}" for i in range(output_tabs.count())]
    active_index = output_tabs.currentIndex() if output_tabs.currentIndex() >= 0 else 0
    return {
        "tabs": tab_titles if tab_titles else ["Result 1"],
        "active_index": active_index,
    }


def restore_output_tabs(manager, tab_content, output_data):
    output_tabs = ensure_output_tabs_widget(manager, tab_content)
    if not output_tabs:
        return

    for idx in range(output_tabs.count()):
        _stop_chunk_loader_for_container(output_tabs.widget(idx))

    output_tabs.blockSignals(True)
    output_tabs.clear()

    saved_titles = []
    if isinstance(output_data, dict):
        saved_titles = output_data.get("tabs", []) or []

    if not saved_titles:
        saved_titles = ["Result 1"]

    for title in saved_titles:
        create_output_tab(manager, tab_content, title=str(title), activate=False)

    active_index = 0
    if isinstance(output_data, dict):
        active_index = output_data.get("active_index", 0)
    if active_index < 0 or active_index >= output_tabs.count():
        active_index = 0
    output_tabs.setCurrentIndex(active_index)
    output_tabs.blockSignals(False)


def ensure_default_output_tab(manager, tab_content):
    output_tabs = ensure_output_tabs_widget(manager, tab_content)
    if not output_tabs:
        return None
    return output_tabs


def stop_all_chunk_loaders_for_tab(manager, tab_content):
    output_tabs = get_output_tabs_widget(manager, tab_content)
    if not output_tabs:
        return
    for idx in range(output_tabs.count()):
        _stop_chunk_loader_for_container(output_tabs.widget(idx))
