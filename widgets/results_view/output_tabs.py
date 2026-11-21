from collections import Counter
from PySide6.QtCore import QObject, QSize, Qt, QRect
from PySide6.QtGui import (
    QColor,
    QPalette,
    QPainter,
    QFont,
    QPen,
    QBrush,
    QFontMetrics,
)
from ui.icons import get_icon
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)


def _update_tabs_closability(output_tabs):
    if output_tabs:
        output_tabs.setTabsClosable(output_tabs.count() > 1)


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


class ResultsHeaderView(QHeaderView):
    """
    Modern horizontal header for results table inspired by DataGrip and DBeaver:
    - Top line: Bold column name with visual PK / FK / RO pill badges and red * for NOT NULL
    - Bottom line: Monospace data type in a distinct subtle slate hue
    """
    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setSectionsClickable(True)
        self.setHighlightSections(False)

    def sizeHint(self):
        s = super().sizeHint()
        return QSize(s.width(), 44)

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        model = self.model()
        header_text = str(model.headerData(logicalIndex, Qt.Orientation.Horizontal) or "") if model else ""
        lines = header_text.split("\n")
        full_name = lines[0].strip() if lines else ""
        dtype = lines[1].strip() if len(lines) > 1 else ""

        # Header section background
        painter.fillRect(rect, QColor("#F8FAFC"))

        # Right subtle divider & bottom border
        painter.setPen(QPen(QColor("#E2E8F0"), 1))
        painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        # Parse column metadata badges: [PK], [FK], [RO], *
        tag = None
        tag_bg = None
        tag_fg = None
        is_required = False

        if "[PK]" in full_name:
            tag = "PK"
            tag_bg = QColor("#E0E7FF")
            tag_fg = QColor("#3730A3")
            full_name = full_name.replace("[PK]", "").strip()
        elif "[FK]" in full_name:
            tag = "FK"
            tag_bg = QColor("#E0F2FE")
            tag_fg = QColor("#0369A1")
            full_name = full_name.replace("[FK]", "").strip()
        elif "[RO]" in full_name:
            tag = "RO"
            tag_bg = QColor("#F1F5F9")
            tag_fg = QColor("#64748B")
            full_name = full_name.replace("[RO]", "").strip()

        if full_name.endswith("*"):
            is_required = True
            full_name = full_name[:-1].strip()

        pad_x = 10
        cur_x = rect.left() + pad_x
        top_y = rect.top() + 6

        # 1. Column Name (Bold slate-900)
        name_font = QFont("Segoe UI", 9)
        name_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(name_font)
        painter.setPen(QColor("#0F172A"))
        fm_name = QFontMetrics(name_font)
        avail_name_w = rect.width() - (pad_x * 2) - (35 if tag else 0) - (10 if is_required else 0)
        disp_name = fm_name.elidedText(full_name, Qt.TextElideMode.ElideRight, max(avail_name_w, 20))
        disp_name_w = fm_name.horizontalAdvance(disp_name)
        painter.drawText(cur_x, top_y + 14, disp_name)
        cur_x += disp_name_w + 3

        # 2. Required Asterisk
        if is_required and cur_x < rect.right() - 25:
            ast_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
            painter.setFont(ast_font)
            painter.setPen(QColor("#DC2626"))
            painter.drawText(cur_x, top_y + 14, "*")
            cur_x += 8

        # 3. Constraint Badge (PK / FK / RO pill)
        if tag and cur_x < rect.right() - 24:
            cur_x += 4
            badge_w = 20
            badge_h = 13
            badge_rect = QRect(cur_x, top_y + 2, badge_w, badge_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(tag_bg))
            painter.drawRoundedRect(badge_rect, 3, 3)
            badge_font = QFont("Segoe UI", 7, QFont.Weight.Bold)
            painter.setFont(badge_font)
            painter.setPen(tag_fg)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, tag)

        # 4. Data Type (Subtle secondary monospace label)
        if dtype:
            bot_y = rect.top() + 25
            dt_font = QFont("Consolas", 8)
            painter.setFont(dt_font)
            fm_dt = QFontMetrics(dt_font)
            avail_dt_w = rect.width() - (pad_x * 2)
            disp_dt = fm_dt.elidedText(dtype, Qt.TextElideMode.ElideRight, max(avail_dt_w, 10))
            painter.setPen(QColor("#64748B"))
            painter.drawText(rect.left() + pad_x, bot_y + 11, disp_dt)

        painter.restore()


class FlatSelectionDelegate(QStyledItemDelegate):
    """Paints result-table selection with a soft, eye-friendly light blue."""

    ROW_HEIGHT: int = 28

    def __init__(
        self,
        selection_color="#D4E0EE",
        hover_color="#EBF3FA",
        text_color="#0F172A",
        parent=None,
        row_height: int = ROW_HEIGHT,
    ):
        if isinstance(selection_color, QObject) and parent is None:
            parent = selection_color
            selection_color = "#D4E0EE"
        super().__init__(parent)
        self.selection_color = QColor(selection_color)
        self.hover_color = QColor(hover_color)
        self.text_color = QColor(text_color)
        self.row_height = row_height

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        """Enforces uniform 28px row height across all cells while preserving column width calculation."""
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), self.row_height)

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
            painter.fillRect(option.rect, self.hover_color)
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
            paint_option.palette.setColor(QPalette.ColorRole.Text, self.text_color)
        super().paint(painter, paint_option, index)
        painter.restore()

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.setFrame(False)
            editor.setObjectName("results_table_delegate_editor")
        return editor

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


def create_readonly_banner(parent=None):
    banner = QFrame(parent)
    banner.setObjectName("readonly_banner")
    layout = QHBoxLayout(banner)
    layout.setContentsMargins(8, 2, 8, 2)
    layout.setSpacing(8)

    icon_label = QLabel()
    icon_label.setObjectName("readonly_banner_icon")
    icon_label.setPixmap(get_icon("msc.lock", color="#B45309").pixmap(12, 12))
    layout.addWidget(icon_label)

    msg_label = QLabel("")
    msg_label.setObjectName("readonly_banner_label")
    layout.addWidget(msg_label, 1)

    close_btn = QPushButton()
    close_btn.setObjectName("readonly_banner_close")
    close_btn.setFixedSize(18, 18)
    close_btn.setIcon(get_icon("msc.close", color="#B45309"))
    close_btn.setIconSize(QSize(10, 10))
    close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    close_btn.setToolTip("Dismiss notice")
    close_btn.clicked.connect(banner.hide)
    layout.addWidget(close_btn)

    banner.hide()
    return banner


def create_output_tabs_view(manager, tab_content):
    output_tabs = QTabWidget()
    output_tabs.setObjectName("output_tabs")
    output_tabs.setTabsClosable(True)
    output_tabs.setMovable(False)
    output_tabs.setTabBarAutoHide(False)
    output_tabs.setDocumentMode(True)
    output_tabs.tabCloseRequested.connect(lambda index: manager._handle_output_tab_close(tab_content, index))
    output_tabs.currentChanged.connect(lambda _index: manager.sync_row_action_state(tab_content))
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
    output_tabs.currentChanged.connect(lambda _index: manager.sync_row_action_state(tab_content))

    results_info_bar = tab_content.findChild(QWidget, "resultsInfoBar")
    if results_info_bar:
        output_tabs.setCornerWidget(results_info_bar, Qt.Corner.TopRightCorner)

    output_container = QWidget()
    output_layout = QVBoxLayout(output_container)
    output_layout.setContentsMargins(0, 0, 0, 0)
    output_layout.setSpacing(0)

    banner = create_readonly_banner(output_container)
    output_layout.addWidget(banner)

    existing_table = old_page_zero.findChild(QTableView, "results_table") if old_page_zero else None
    if existing_table:
        existing_table.setParent(None)
        output_layout.addWidget(existing_table)
    else:
        output_layout.addWidget(create_output_table_view(manager, tab_content))

    output_container.setProperty("tab_base_name", "Result")
    output_tabs.addTab(output_container, "Result")
    output_tabs.setCurrentIndex(0)
    _update_tabs_closability(output_tabs)

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
        if not output_container.findChild(QFrame, "readonly_banner"):
            output_layout.addWidget(create_readonly_banner(output_container))
        table_view = create_output_table_view(manager, tab_content)
        output_layout.addWidget(table_view)

    return table_view, output_tabs.currentIndex()


class ResultsTableView(QTableView):
    """QTableView subclass with keyboard shortcuts for cell inspection and editing."""

    ROW_HEIGHT: int = 28

    def __init__(self, manager=None, tab_content=None, parent=None):
        super().__init__(parent)
        self._results_manager = manager
        self._tab_content = tab_content

    def sizeHintForRow(self, row: int) -> int:
        """Enforces uniform 28px row height hint to prevent view engines from expanding rows."""
        return self.ROW_HEIGHT

    def _is_cell_editable(self, index) -> bool:
        """Determines if a given model index can be edited in place."""
        if not index.isValid():
            return False
        output_state = self.property("output_state") or {}
        if not output_state.get("is_editable", False):
            return False
        col = index.column()
        column_specs = output_state.get("column_specs") or []
        if 0 <= col < len(column_specs) and column_specs[col].get("read_only"):
            return False
        model = self.model()
        if not model:
            return False
        return bool(model.flags(index) & Qt.ItemFlag.ItemIsEditable)

    def _is_content_larger_than_cell(self, index) -> bool:
        """Returns True only if the content is larger, wider, or taller than the cell boundaries."""
        if not index.isValid():
            return False

        col = index.column()
        output_state = self.property("output_state") or {}
        column_specs = output_state.get("column_specs") or []
        if 0 <= col < len(column_specs):
            data_type = str(column_specs[col].get("data_type") or "").lower()
            if any(k in data_type for k in ("json", "xml", "clob", "blob", "bytea")):
                return True

        raw_val = index.data(Qt.ItemDataRole.EditRole)
        if raw_val is None:
            raw_val = index.data(Qt.ItemDataRole.DisplayRole)
        if raw_val is None or raw_val == "NULL":
            return False

        text = str(raw_val)
        if not text:
            return False

        # Multiline text is taller than a single 28px row
        if "\n" in text or "\r" in text:
            return True

        # Check if text pixel width exceeds visible column width
        col_width = self.columnWidth(col)
        if col_width <= 0 and self.horizontalHeader():
            col_width = self.horizontalHeader().defaultSectionSize()
        if col_width <= 0:
            col_width = 100

        text_pixel_width = self.fontMetrics().horizontalAdvance(text)
        if text_pixel_width + 16 > col_width:
            return True

        # Structured JSON or XML blocks
        s = text.strip()
        if (
            (s.startswith("{") and s.endswith("}"))
            or (s.startswith("[") and s.endswith("]"))
            or (s.startswith("<") and s.endswith(">"))
        ):
            return True

        if len(text) > 80:
            return True

        return False

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            index = self.indexAt(pos)
            if index.isValid():
                if self.state() == QAbstractItemView.State.EditingState:
                    active_editors = [w for w in self.findChildren(QLineEdit) if w.isVisible()]
                    if not active_editors:
                        viewport = self.viewport()
                        if viewport:
                            active_editors = [
                                w for w in viewport.children()
                                if isinstance(w, QWidget) and w.isVisible()
                            ]
                            if not active_editors:
                                active_editors = [
                                    w for w in viewport.findChildren(QWidget)
                                    if w.isVisible() and w is not viewport
                                ]
                    if active_editors:
                        for editor in active_editors:
                            try:
                                self.commitData(editor)
                            finally:
                                try:
                                    self.closeEditor(editor, QAbstractItemDelegate.EndEditHint.SubmitModelCache)
                                finally:
                                    try:
                                        editor.hide()
                                    except Exception:
                                        pass
                    if self.state() == QAbstractItemView.State.EditingState:
                        self.setState(QAbstractItemView.State.NoState)

                self.setCurrentIndex(index)
                is_larger = self._is_content_larger_than_cell(index)
                is_editable = self._is_cell_editable(index)

                if is_larger:
                    # Content is larger/wider than cell -> pop up the editor/viewer dialog
                    if self._results_manager and hasattr(self._results_manager, "open_cell_value_viewer"):
                        self._results_manager.open_cell_value_viewer(self)
                elif is_editable:
                    # Small, single-line editable value (e.g. 1 number, short word) -> edit in-cell
                    self.edit(index)
                else:
                    # Small value in a read-only table that fits in the cell:
                    # Content is already fully visible, do not open an unnecessary dialog.
                    pass
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if self.state() != QAbstractItemView.State.EditingState:
            key = event.key()
            modifiers = event.modifiers()
            cmd_alt_meta = (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
            is_space = (
                key == Qt.Key.Key_Space
                and not bool(modifiers & (Qt.KeyboardModifier.ShiftModifier | cmd_alt_meta))
            )
            is_shift_enter = (
                key in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
                and not bool(modifiers & cmd_alt_meta)
            )
            is_f7 = key == Qt.Key.Key_F7
            if is_space or is_shift_enter or is_f7:
                if self._results_manager and hasattr(self._results_manager, "open_cell_value_viewer"):
                    self._results_manager.open_cell_value_viewer(self)
                    event.accept()
                    return

            no_mods = not bool(modifiers & (Qt.KeyboardModifier.ShiftModifier | cmd_alt_meta))
            is_plain_enter = key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and no_mods
            is_f2 = key == Qt.Key.Key_F2 and no_mods
            if is_plain_enter or is_f2:
                curr = self.currentIndex()
                if not curr.isValid():
                    selected = self.selectedIndexes()
                    if selected:
                        curr = selected[0]
                        self.setCurrentIndex(curr)
                if curr.isValid():
                    if bool(curr.flags() & Qt.ItemFlag.ItemIsEditable):
                        self.edit(curr)
                    elif (
                        self._results_manager
                        and hasattr(self._results_manager, "status")
                        and self._results_manager.status
                    ):
                        self._results_manager.status.showMessage("Cell is read-only", 3000)
                    event.accept()
                    return

        super().keyPressEvent(event)


def create_output_table_view(manager, tab_content):
    table_view = ResultsTableView(manager, tab_content)
    table_view.setObjectName("results_table")
    table_view.setHorizontalHeader(ResultsHeaderView(table_view))
    table_view.setAlternatingRowColors(True)
    table_view.setMouseTracking(True)
    table_view.viewport().setMouseTracking(True)
    table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
    table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    table_view.horizontalHeader().setSectionsClickable(True)
    table_view.horizontalHeader().setHighlightSections(False)
    table_view.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    table_view.verticalHeader().setSectionsClickable(True)
    table_view.verticalHeader().setDefaultSectionSize(28)
    table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
    show_row_numbers = bool(
        getattr(getattr(manager, "main_window", None), "grid_show_row_numbers", True)
    )
    table_view.verticalHeader().setVisible(show_row_numbers)
    table_view.setItemDelegate(FlatSelectionDelegate(parent=table_view))
    table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    table_view.customContextMenuRequested.connect(manager.show_results_context_menu)
    table_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    output_state = {
        "table_name": None,
        "qualified_table_name": None,
        "real_table_name": None,
        "schema_name": None,
        "is_editable": False,
        "readonly_reason": None,
        "readonly_reason_code": None,
        "column_names": [],
        "modified_coords": set(),
        "new_row_index": None,
        "cached_proxy_model": None,
    }
    table_view.setProperty("output_state", output_state)
    table_view.doubleClicked.connect(
        lambda index: manager.handle_results_double_click(table_view, index, tab_content)
        if hasattr(manager, "handle_results_double_click")
        else None
    )
    return table_view


def _refresh_tab_titles(output_tabs: QTabWidget) -> None:
    """Re-label every tab: show a number suffix only when the base name appears more than once."""
    base_names = [
        output_tabs.widget(i).property("tab_base_name") or "Result"
        for i in range(output_tabs.count())
    ]
    counts = Counter(base_names)
    seen: dict[str, int] = {}
    for i in range(output_tabs.count()):
        base = base_names[i]
        if counts[base] > 1:
            seen[base] = seen.get(base, 0) + 1
            output_tabs.setTabText(i, f"{base} {seen[base]}")
        else:
            output_tabs.setTabText(i, base)


def create_output_tab(manager, tab_content, title=None, activate=True):
    output_tabs = ensure_output_tabs_widget(manager, tab_content)
    if not output_tabs:
        return None

    output_container = QWidget()
    output_layout = QVBoxLayout(output_container)
    output_layout.setContentsMargins(0, 0, 0, 0)
    output_layout.setSpacing(0)

    banner = create_readonly_banner(output_container)
    output_layout.addWidget(banner)

    table_view = create_output_table_view(manager, tab_content)
    output_layout.addWidget(table_view)

    base_name = title or "Result"
    output_container.setProperty("tab_base_name", base_name)
    new_index = output_tabs.addTab(output_container, base_name)
    _refresh_tab_titles(output_tabs)
    if activate:
        output_tabs.setCurrentIndex(new_index)
    _update_tabs_closability(output_tabs)
    return new_index


def add_output_tab_with_table_name(manager, tab_content, query=None, table_name=None, activate=True):
    output_tabs = ensure_output_tabs_widget(manager, tab_content)
    if not output_tabs:
        return None

    resolved_table_name = table_name
    if not resolved_table_name and query:
        resolved_table_name = manager._extract_query_table_name(query)

    base_name = resolved_table_name if resolved_table_name else "Result"
    return create_output_tab(manager, tab_content, title=base_name, activate=activate)


def ensure_at_least_one_output_tab(manager, tab_content):
    output_tabs = ensure_output_tabs_widget(manager, tab_content)
    if output_tabs and output_tabs.count() == 0:
        output_container = QWidget()
        output_layout = QVBoxLayout(output_container)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(0)
        banner = create_readonly_banner(output_container)
        output_layout.addWidget(banner)
        table_view = create_output_table_view(manager, tab_content)
        output_layout.addWidget(table_view)
        output_container.setProperty("tab_base_name", "Result")
        output_tabs.addTab(output_container, "Result")
        _refresh_tab_titles(output_tabs)
        output_tabs.setCurrentIndex(0)
        _update_tabs_closability(output_tabs)


def set_output_tab_title(manager, tab_content, output_tab_index, query):
    output_tabs = ensure_output_tabs_widget(manager, tab_content)
    if not output_tabs or output_tab_index is None:
        return
    if output_tab_index < 0 or output_tab_index >= output_tabs.count():
        return

    table_name = manager._extract_query_table_name(query)
    base_name = table_name if table_name else "Result"

    container = output_tabs.widget(output_tab_index)
    if container:
        container.setProperty("tab_base_name", base_name)
    _refresh_tab_titles(output_tabs)


def handle_output_tab_close(manager, tab_content, index):
    output_tabs = ensure_output_tabs_widget(manager, tab_content)
    if not output_tabs:
        return
    if output_tabs.count() <= 1:
        return
    output_container = output_tabs.widget(index)
    if output_container:
        table = output_container.findChild(QTableView, "results_table")
        if table:
            output_state = table.property("output_state") or {}
            if output_state.get("modified_coords") or output_state.get("new_row_index") is not None:
                if hasattr(manager, "check_unsaved_changes_before_action"):
                    if not manager.check_unsaved_changes_before_action(tab_content, "closing this result tab"):
                        return
    _stop_chunk_loader_for_container(output_container)
    output_tabs.removeTab(index)
    if output_tabs.count() == 0:
        create_output_tab(manager, tab_content, title="Result", activate=True)
    else:
        _refresh_tab_titles(output_tabs)
        _update_tabs_closability(output_tabs)
    manager.sync_row_action_state(tab_content)


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
