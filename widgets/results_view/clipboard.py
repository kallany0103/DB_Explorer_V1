from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QTableView, QTextEdit


def copy_current_result_table(manager):
    tab = manager.tab_widget.currentWidget()
    if not tab:
        return

    table_view = manager._get_result_table_for_tab(tab)
    if not table_view:
        return

    copy_result_with_header(manager, table_view)


def copy_result_with_header(manager, table_view: QTableView):
    model = table_view.model()
    sel = table_view.selectionModel()

    if not model or not sel:
        return

    rows = []

    selected_rows = sel.selectedRows()
    selected_indexes = sel.selectedIndexes()

    if selected_rows:
        columns = range(model.columnCount())

        header = [
            str(model.headerData(col, Qt.Orientation.Horizontal) or "")
            for col in columns
        ]
        rows.append("\t".join(header))

        for selected_row in selected_rows:
            row = selected_row.row()
            row_data = [
                str(model.index(row, col).data() or "")
                for col in columns
            ]
            rows.append("\t".join(row_data))
    elif selected_indexes:
        selected_indexes = sorted(
            selected_indexes, key=lambda index: (index.row(), index.column())
        )

        columns = sorted({index.column() for index in selected_indexes})

        header = [
            str(model.headerData(col, Qt.Orientation.Horizontal) or "")
            for col in columns
        ]
        rows.append("\t".join(header))

        current_row = selected_indexes[0].row()
        row_data = []

        for index in selected_indexes:
            if index.row() != current_row:
                rows.append("\t".join(row_data))
                row_data = []
                current_row = index.row()

            row_data.append(str(index.data() or ""))

        rows.append("\t".join(row_data))
    else:
        return

    QApplication.clipboard().setText("\n".join(rows))


def paste_to_editor(manager):
    editor = get_current_editor(manager)
    if editor:
        editor.paste()


def get_current_editor(manager):
    current_tab = manager.tab_widget.currentWidget()
    if not current_tab:
        return None
    return current_tab.findChild(QTextEdit, "query_editor")
