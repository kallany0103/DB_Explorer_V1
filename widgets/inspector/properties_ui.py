from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFormLayout, 
    QFrame, QStyledItemDelegate, QComboBox,
    QLineEdit, QAbstractItemView, QStyle, QStyleOptionViewItem, QHeaderView, QScrollArea
)
from PySide6.QtCore import Qt, QRect, QPoint, QEvent
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPalette, QStandardItemModel, QStandardItem
from ui.icons import get_icon
from ui.components import PropertyTable, SearchBox
from widgets.results_view.output_tabs import FlatSelectionDelegate

__all__ = [
    "DataTypeDelegate",
    "POSTGRES_DATA_TYPES",
    "ORACLE_DATA_TYPES",
    "CheckboxDelegate",
    "PropertyCellDelegate",
    "CollapsibleCard",
    "CollectionCard",
    "PropertyTable",
    "HIDDEN_PROPERTY_KEYS",
    "PROPERTY_LABELS",
]


class CheckboxDelegate(QStyledItemDelegate):
    """
    Renders and manages interactive, modern checkboxes for boolean columns
    (PK, Not Null) in table property sheets.
    - Renders a crisp 16x16 checkbox on every row.
    - Unchecked: #FFFFFF background with #94A3B8 border (highlights #0284C7 on hover/focus).
    - Checked: #0284C7 background with crisp white vector checkmark.
    - Draws cell selection background and active cell focus border.
    - Click anywhere in cell or press Space to toggle.
    """
    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        has_focus = bool(option.state & QStyle.StateFlag.State_HasFocus) or (
            option.widget and option.widget.currentIndex() == index
        )

        # 1. Background
        if is_selected:
            painter.fillRect(option.rect, QColor("#D4E0EE"))
        elif is_hovered:
            painter.fillRect(option.rect, QColor("#F1F5F9"))

        # 2. Cell focus border
        if has_focus:
            painter.setPen(QPen(QColor("#0284C7"), 1.5))
            painter.drawRect(option.rect.adjusted(1, 1, -1, -1))

        # 3. 16x16 Checkbox
        box_size = 16
        bx = option.rect.center().x() - box_size // 2
        by = option.rect.center().y() - box_size // 2
        box_rect = QRect(bx, by, box_size, box_size)

        is_checked = bool(index.data(Qt.ItemDataRole.UserRole))

        if is_checked:
            painter.setPen(QPen(QColor("#0284C7"), 1))
            painter.setBrush(QBrush(QColor("#0284C7")))
            painter.drawRoundedRect(box_rect, 3, 3)

            check_pen = QPen(
                QColor("#FFFFFF"), 2, Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
            )
            painter.setPen(check_pen)
            p1 = box_rect.topLeft() + QPoint(4, 8)
            p2 = box_rect.topLeft() + QPoint(7, 11)
            p3 = box_rect.topLeft() + QPoint(12, 5)
            painter.drawLine(p1, p2)
            painter.drawLine(p2, p3)
        else:
            border_color = QColor("#0284C7") if (is_hovered or has_focus) else QColor("#94A3B8")
            painter.setPen(QPen(border_color, 1.5))
            painter.setBrush(QBrush(QColor("#FFFFFF")))
            painter.drawRoundedRect(box_rect.adjusted(0, 0, -1, -1), 3, 3)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
            if event.button() == Qt.MouseButton.LeftButton:
                val = not bool(index.data(Qt.ItemDataRole.UserRole))
                model.setData(index, val, Qt.ItemDataRole.UserRole)
                return True
        elif event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Space:
                val = not bool(index.data(Qt.ItemDataRole.UserRole))
                model.setData(index, val, Qt.ItemDataRole.UserRole)
                return True
        return super().editorEvent(event, model, option, index)


POSTGRES_DATA_TYPES = [
    # Character / String
    "VARCHAR(255)",
    "VARCHAR",
    "TEXT",
    "CHAR(1)",
    "CHAR",
    "CHARACTER VARYING",
    # Numeric
    "INTEGER",
    "BIGINT",
    "SMALLINT",
    "NUMERIC",
    "NUMERIC(10,2)",
    "DECIMAL",
    "REAL",
    "DOUBLE PRECISION",
    "SERIAL",
    "BIGSERIAL",
    "SMALLSERIAL",
    "MONEY",
    # Date / Time
    "DATE",
    "TIME",
    "TIMETZ",
    "TIME WITH TIME ZONE",
    "TIMESTAMP",
    "TIMESTAMPTZ",
    "TIMESTAMP WITH TIME ZONE",
    "INTERVAL",
    # JSON / Binary / Network / Identifiers
    "BOOLEAN",
    "JSONB",
    "JSON",
    "UUID",
    "BYTEA",
    "INET",
    "CIDR",
    "MACADDR",
]

ORACLE_DATA_TYPES = [
    # Strings / Character
    "VARCHAR2(255)",
    "VARCHAR2(4000)",
    "VARCHAR2",
    "CHAR(1)",
    "CHAR",
    "NVARCHAR2(255)",
    "NVARCHAR2",
    "NCHAR(1)",
    "NCHAR",
    "CLOB",
    "NCLOB",
    # Numbers
    "NUMBER",
    "NUMBER(10,2)",
    "NUMBER(38)",
    "INTEGER",
    "FLOAT",
    "BINARY_FLOAT",
    "BINARY_DOUBLE",
    # Date / Time
    "DATE",
    "TIMESTAMP",
    "TIMESTAMP WITH TIME ZONE",
    "TIMESTAMP WITH LOCAL TIME ZONE",
    "INTERVAL YEAR TO MONTH",
    "INTERVAL DAY TO SECOND",
    # Binary / LOB / Raw
    "BLOB",
    "RAW(2000)",
    "RAW",
    "LONG",
    "BFILE",
    # Modern / Other
    "BOOLEAN",
    "JSON",
    "XMLTYPE",
    "ROWID",
    "UROWID",
]


class DataTypeDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, db_type: str = "postgres"):
        super().__init__(parent)
        self.db_type = (db_type or "postgres").lower()
        if "oracle" in self.db_type:
            self.data_types = list(ORACLE_DATA_TYPES)
        else:
            self.data_types = list(POSTGRES_DATA_TYPES)

    def paint(self, painter, option, index):
        is_editing = False
        if option.widget and option.widget.state() == QAbstractItemView.State.EditingState:
            curr = option.widget.currentIndex()
            if curr.isValid() and curr.row() == index.row() and curr.column() == index.column():
                is_editing = True

        painter.save()
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        has_focus = bool(option.state & QStyle.StateFlag.State_HasFocus) or (
            option.widget and option.widget.currentIndex() == index
        )

        if is_selected:
            painter.fillRect(option.rect, QColor("#D4E0EE"))
        elif is_hovered:
            painter.fillRect(option.rect, QColor("#F1F5F9"))

        if has_focus and not is_editing:
            painter.setPen(QPen(QColor("#0284C7"), 1.5))
            painter.drawRect(option.rect.adjusted(1, 1, -1, -1))

        if not is_editing:
            paint_option = QStyleOptionViewItem(option)
            paint_option.state &= ~QStyle.StateFlag.State_Selected
            paint_option.state &= ~QStyle.StateFlag.State_MouseOver
            paint_option.state &= ~QStyle.StateFlag.State_HasFocus
            if is_selected or is_hovered:
                paint_option.palette.setColor(QPalette.ColorRole.Text, QColor("#0F172A"))
            super().paint(painter, paint_option, index)

        painter.restore()

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.setEditable(True)
        editor.setAutoFillBackground(True)

        curr_val = str(index.model().data(index, Qt.ItemDataRole.EditRole) or "").strip().upper()
        items = list(self.data_types)
        if curr_val and curr_val not in items:
            items.insert(0, curr_val)

        editor.addItems(items)
        if curr_val:
            editor.setCurrentText(curr_val)

        editor.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                color: #0f172a;
                border: 1.5px solid #0284c7;
                border-radius: 3px;
                padding: 1px 6px;
                font-size: 9pt;
                min-height: 22px;
                max-height: 26px;
            }
            QComboBox:focus {
                border: 1.5px solid #0284c7;
                background-color: #ffffff;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                border: none;
            }
            QComboBox::down-arrow {
                image: url(assets/toolbar-chevron-down.svg);
                width: 9px;
                height: 9px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #0f172a;
                selection-background-color: #d4e0ee;
                selection-color: #0f172a;
                border: 1px solid #cbd5e1;
                outline: none;
                padding: 2px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 22px;
                padding: 2px 6px;
            }
        """)
        if editor.lineEdit():
            editor.lineEdit().setStyleSheet("background-color: #ffffff; color: #0f172a; border: none; padding: 0px;")

        # Ensure dropdown popup is wide enough to display any long data type on one single line without elision
        view = editor.view()
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
        fm = editor.fontMetrics()
        max_item_w = max((fm.horizontalAdvance(item) for item in items), default=140)
        # 42px margin for item padding, borders, and vertical scrollbar
        cell_w = option.rect.width() if (option is not None and hasattr(option, "rect")) else 180
        min_popup_w = max(cell_w, max_item_w + 42)
        view.setMinimumWidth(min_popup_w)

        return editor

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect.adjusted(1, 1, -1, -1))

    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        val_str = str(value).strip().upper() if value is not None else ""
        editor.setCurrentText(val_str)

    def setModelData(self, editor, model, index):
        value = editor.currentText().strip().upper()
        model.setData(index, value, Qt.ItemDataRole.EditRole)


class PropertyCellDelegate(QStyledItemDelegate):
    """
    Renders text cells with active focus border, clear selection color,
    and cleanly bounded in-cell editors without text ghosting.
    """
    def paint(self, painter, option, index):
        is_editing = False
        if option.widget and option.widget.state() == QAbstractItemView.State.EditingState:
            curr = option.widget.currentIndex()
            if curr.isValid() and curr.row() == index.row() and curr.column() == index.column():
                is_editing = True

        painter.save()
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        has_focus = bool(option.state & QStyle.StateFlag.State_HasFocus) or (
            option.widget and option.widget.currentIndex() == index
        )

        if is_selected:
            painter.fillRect(option.rect, QColor("#D4E0EE"))
        elif is_hovered:
            painter.fillRect(option.rect, QColor("#F1F5F9"))

        if has_focus and not is_editing:
            painter.setPen(QPen(QColor("#0284C7"), 1.5))
            painter.drawRect(option.rect.adjusted(1, 1, -1, -1))

        if not is_editing:
            paint_option = QStyleOptionViewItem(option)
            paint_option.state &= ~QStyle.StateFlag.State_Selected
            paint_option.state &= ~QStyle.StateFlag.State_MouseOver
            paint_option.state &= ~QStyle.StateFlag.State_HasFocus
            if is_selected or is_hovered:
                paint_option.palette.setColor(QPalette.ColorRole.Text, QColor("#0F172A"))
            super().paint(painter, paint_option, index)

        painter.restore()

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.setAutoFillBackground(True)
            editor.setStyleSheet("""
                QLineEdit {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1.5px solid #0284c7;
                    border-radius: 3px;
                    padding: 2px 6px;
                    font-size: 9pt;
                }
            """)
        return editor

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect.adjusted(1, 1, -1, -1))


HIDDEN_PROPERTY_KEYS = frozenset({
    "oid", "relkind", "reltablespace", "nspname", "sql", "schema_name",
})

PROPERTY_LABELS = {
    "owner": "Owner",
    "comment": "Comment",
    "rows_estimated": "Estimated rows",
    "is_partitioned": "Partitioned",
    "table_name": "Table",
    "function_name": "Trigger Function",
    "status": "Status",
    "timing": "Timing",
    "events": "Events",
    "level": "Level",
}


class CollapsibleCard(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("propertyCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.header = QLabel(title)
        self.header.setObjectName("cardHeader")
        self.header.setProperty("active", True)
        layout.addWidget(self.header)
        
        self.content_widget = QWidget()
        self.content_widget.setObjectName("cardContentWidget")
        self.content_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(16, 14, 16, 14)
        layout.addWidget(self.content_widget)
        
        self.form_layout = QFormLayout()
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form_layout.setSpacing(10)
        self.content_layout.addLayout(self.form_layout)

    def add_row(self, label_text, value_widget):
        label = QLabel(label_text)
        label.setStyleSheet("color: #475569; font-weight: 500; font-size: 9pt;")
        
        if not isinstance(value_widget, QWidget):
            if value_widget is None:
                text = ""
            elif isinstance(value_widget, bool):
                text = "Yes" if value_widget else "No"
            elif hasattr(value_widget, "strftime"):
                text = value_widget.strftime("%Y-%m-%d %H:%M:%S")
            else:
                text = str(value_widget)
            val = QLabel(text)
            val.setWordWrap(True)
            val.setMinimumHeight(26)
            val.setStyleSheet("color: #0f172a; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 3px 8px; font-size: 9pt;")
            value_widget = val
            
        self.form_layout.addRow(label, value_widget)


class CollectionCard(QFrame):
    """
    Structured card container for collection tables (Schemas, Tables, Views).
    Wraps the table inside a rounded #propertyCard with #cardHeaderFrame toolbar
    (title, item count badge, and SearchBox), proportional column widths, and
    clean boolean formatting.
    """
    def __init__(self, title: str, columns: list, rows: list, parent=None):
        super().__init__(parent)
        self.title_text = title
        self.columns_data = columns or []
        self.rows_data = rows or []
        self._user_resized_columns = False
        self._is_programmatic_resize = False

        self.setObjectName("propertyCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header toolbar
        self.header_frame = QFrame()
        self.header_frame.setObjectName("cardHeaderFrame")
        self.header_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.header_frame.setFixedHeight(40)
        h_layout = QHBoxLayout(self.header_frame)
        h_layout.setContentsMargins(14, 0, 14, 0)
        h_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        h_layout.setSpacing(8)

        self.title_label = QLabel(self.title_text)
        self.title_label.setObjectName("cardHeaderTitle")
        self.title_label.setStyleSheet(
            "color: #0284c7; font-weight: 600; font-size: 10pt; border: none; background: transparent;"
        )
        h_layout.addWidget(self.title_label)

        self.count_label = QLabel(f"({len(self.rows_data)})")
        self.count_label.setStyleSheet(
            "color: #64748b; font-weight: 500; font-size: 9pt; border: none; background: transparent;"
        )
        h_layout.addWidget(self.count_label)

        h_layout.addStretch()

        self.search = SearchBox(placeholder=f"Search {self.title_text.lower()}...")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(220)
        self.search.setFixedHeight(28)
        h_layout.addWidget(self.search)

        layout.addWidget(self.header_frame)

        # Empty state container
        self.empty_widget = QWidget()
        self.empty_widget.setObjectName("cardEmptyWidget")
        self.empty_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setContentsMargins(20, 28, 20, 28)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(6)

        self.empty_icon = QLabel()
        self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_icon.setStyleSheet("border: none; background: transparent;")
        empty_layout.addWidget(self.empty_icon)

        self.empty_title = QLabel()
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title.setStyleSheet("font-size: 10pt; font-weight: 600; color: #334155; border: none; background: transparent;")
        empty_layout.addWidget(self.empty_title)

        self.empty_subtitle = QLabel()
        self.empty_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_subtitle.setStyleSheet("font-size: 9pt; color: #64748b; border: none; background: transparent;")
        empty_layout.addWidget(self.empty_subtitle)

        layout.addWidget(self.empty_widget)

        # Table
        self.table = PropertyTable()
        self.table.setObjectName("collectionTable")
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setItemDelegate(FlatSelectionDelegate(parent=self.table))
        self.table.setAlternatingRowColors(True)

        clean_headers = [
            str(col).replace('_', ' ').replace('?', '').strip().title()
            for col in self.columns_data
        ]
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(clean_headers)

        for row in self.rows_data:
            items = []
            for val in row:
                item = QStandardItem()
                if isinstance(val, bool):
                    item.setText("Yes" if val else "No")
                    item.setForeground(QColor("#0284c7" if val else "#64748b"))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif val is None:
                    item.setText("")
                else:
                    item.setText(str(val))
                items.append(item)
            self.model.appendRow(items)
        self.table.setModel(self.model)

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(True)
        hh.sectionResized.connect(self._on_section_resized)

        layout.addWidget(self.table)

        self.search.textChanged.connect(self._on_search)
        self._update_table_geometry()

    def _find_parent_scroll_area(self):
        p = self.parentWidget()
        while p:
            if isinstance(p, QScrollArea):
                return p
            p = p.parentWidget()
        return None

    def _on_section_resized(self, logical_index, old_size, new_size):
        if not self._is_programmatic_resize and self.isVisible() and self.table.viewport().width() > 0:
            self._user_resized_columns = True

    def showEvent(self, event):
        super().showEvent(event)
        self._update_table_geometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_table_geometry()

    def _update_table_geometry(self):
        visible_rows = 0
        for r in range(self.model.rowCount()):
            if not self.table.isRowHidden(r):
                visible_rows += 1

        if len(self.rows_data) == 0:
            self.table.setVisible(False)
            self.empty_widget.setVisible(True)
            self.empty_widget.setFixedHeight(140)
            self.setFixedHeight(self.header_frame.height() + 140 + 2)
            self.search.setEnabled(False)
            self.empty_icon.setPixmap(get_icon('msc.inbox', color='#94a3b8').pixmap(32, 32))
            self.empty_title.setText(f"No {self.title_text.lower()} found")
            self.empty_subtitle.setText(f"There are no {self.title_text.lower()} in this collection.")
            return

        if visible_rows == 0:
            self.table.setVisible(False)
            self.empty_widget.setVisible(True)
            self.empty_widget.setFixedHeight(140)
            self.setFixedHeight(self.header_frame.height() + 140 + 2)
            self.search.setEnabled(True)
            self.empty_icon.setPixmap(get_icon('msc.search', color='#94a3b8').pixmap(32, 32))
            self.empty_title.setText(f"No matching {self.title_text.lower()}")
            self.empty_subtitle.setText("Try adjusting your search query.")
            return

        self.empty_widget.setVisible(False)
        self.table.setVisible(True)
        self.search.setEnabled(True)

        if not self._user_resized_columns:
            self._adjust_column_widths()

        h_header = self.table.horizontalHeader().height()
        if h_header <= 0:
            h_header = self.table.horizontalHeader().sizeHint().height() or 28
        row_h = self.table.verticalHeader().defaultSectionSize() or 32

        content_h = h_header + (visible_rows * row_h) + 4

        parent_scroll = self._find_parent_scroll_area()
        if parent_scroll and parent_scroll.viewport().height() > 100:
            avail_h = max(200, parent_scroll.viewport().height() - 80)
        else:
            avail_h = 550

        final_table_h = min(content_h, avail_h)
        self.table.setFixedHeight(final_table_h)
        self.setFixedHeight(self.header_frame.height() + final_table_h + 2)

    def _adjust_column_widths(self):
        total_w = self.table.viewport().width()
        if total_w <= 0:
            total_w = max(self.width() - 2, 750)

        num_cols = self.model.columnCount()
        if num_cols == 0:
            return

        self._is_programmatic_resize = True
        try:
            if num_cols == 3:
                w0 = max(240, int(total_w * 0.35))
                w1 = max(180, int(total_w * 0.25))
                self.table.setColumnWidth(0, w0)
                self.table.setColumnWidth(1, w1)
            elif num_cols == 4:
                w0 = max(240, int(total_w * 0.35))
                w1 = max(180, int(total_w * 0.22))
                w2 = 110
                self.table.setColumnWidth(0, w0)
                self.table.setColumnWidth(1, w1)
                self.table.setColumnWidth(2, w2)
            else:
                self.table.resizeColumnsToContents()
        finally:
            self._is_programmatic_resize = False

    def _on_search(self, text):
        t = text.strip().lower()
        visible_count = 0
        for r in range(self.model.rowCount()):
            match = not t or any(
                t in (self.model.item(r, c).text().lower() if self.model.item(r, c) else "")
                for c in range(self.model.columnCount())
            )
            self.table.setRowHidden(r, not match)
            if match:
                visible_count += 1
        if t:
            self.count_label.setText(f"({visible_count} of {len(self.rows_data)})")
        else:
            self.count_label.setText(f"({len(self.rows_data)})")
        self._update_table_geometry()

