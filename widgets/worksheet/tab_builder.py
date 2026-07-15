from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QMenu,
    QComboBox,
    QToolButton,
    QStackedWidget,
    QTextEdit,
    QLabel,
    QAbstractItemView,
    QButtonGroup,
    QTreeView,
    QGroupBox,
    QFrame,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QFont, QIcon, QKeySequence
import qtawesome as qta
from widgets.worksheet.connections import get_connection_icon
from ui.toolbars import WorksheetToolbar, NavigationHeader
from ui.components import SecondaryButton
from widgets.worksheet.code_editor import CodeEditor
from widgets.worksheet.autocomplete import CompletionEngine
from widgets.test_cases.test_cases_widget import TestCasesWidget
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame

def add_tab(manager):
    tab_content = QWidget(manager.tab_widget)
    tab_content.current_limit = 0
    tab_content.current_offset = 0
    tab_content.current_page = 1
    tab_content.has_more_pages = True

    layout = QVBoxLayout(tab_content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    font = QFont()
    font.setBold(True)
    # Unified Connection Selector Frame
    conn_selector_frame = QFrame()
    conn_selector_frame.setObjectName("conn_selector_container")
    conn_selector_frame.setFixedHeight(32)
    conn_selector_frame.setStyleSheet("""
        QFrame#conn_selector_container {
            background-color: #ffffff;
            border: 1px solid #b9b9b9;
            border-radius: 4px;
        }
        QComboBox#db_combo_box {
            border: none;
            background-color: transparent;
            padding: 2px 5px;
            color: #1f2937;
        }
        QComboBox#db_combo_box QAbstractItemView {
            background-color: #ffffff;
            color: #1f2937;
            selection-background-color: #DDE2E8;
            selection-color: #1f2937;
            border: 1px solid #B8BEC6;
            outline: none;
        }
        QComboBox#db_combo_box QAbstractItemView::item {
            padding: 4px 8px;
            color: #1f2937;
        }
        QComboBox#db_combo_box QAbstractItemView::item:hover {
            background-color: #EEF1F6;
            color: #1f2937;
        }
        QComboBox#db_combo_box QAbstractItemView::item:selected {
            background-color: #DDE2E8;
            color: #1f2937;
        }
        QLabel#conn_status_icon {
            background-color: transparent;
            border: none;
            padding-left: 5px;
        }
    """)

    conn_selection_layout = QHBoxLayout(conn_selector_frame)
    conn_selection_layout.setContentsMargins(0, 0, 0, 0)
    conn_selection_layout.setSpacing(0)

    conn_status_icon = QLabel()
    conn_status_icon.setObjectName("conn_status_icon")
    conn_status_icon.setFixedSize(30, 30)
    conn_status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    # Set a default icon pixmap
    conn_status_icon.setPixmap(qta.icon("fa5s.link", color="#72777a").pixmap(16, 16))
    conn_selection_layout.addWidget(conn_status_icon)

    # Vertical Separator
    separator = QFrame()
    separator.setFrameShape(QFrame.Shape.VLine)
    separator.setFrameShadow(QFrame.Shadow.Plain)
    separator.setStyleSheet("color: #D3D3D3; margin: 0px;")
    conn_selection_layout.addWidget(separator)

    from PySide6.QtWidgets import QListView
    db_combo_box = QComboBox()
    db_combo_box.setObjectName("db_combo_box")
    db_combo_box.setView(QListView())
    db_combo_box.setMaxVisibleItems(20)
    _popup_view = db_combo_box.view()
    if _popup_view:
        _popup_view.setCursor(Qt.CursorShape.PointingHandCursor)
    _popup_view.setStyleSheet("""
        QAbstractItemView::item { padding: 4px 8px; color: #1f2937; }
        QAbstractItemView::item:hover { background-color: #EEF1F6; color: #1f2937; }
        QAbstractItemView::item:selected { background-color: #DDE2E8; color: #1f2937; }
    """)
    conn_selection_layout.addWidget(db_combo_box, 1)
    
    # Add the unified frame to the main layout
    layout.addWidget(conn_selector_frame)
    manager.load_joined_connections(db_combo_box)

    def update_conn_status_icon():
        
        data = db_combo_box.currentData()
        if data:
            db_type = data.get("type", "")
            icon = get_connection_icon(db_type)
            conn_status_icon.setPixmap(icon.pixmap(16, 16))
        else:
            conn_status_icon.setPixmap(qta.icon("fa5s.link", color="#72777a").pixmap(16, 16))

    db_combo_box.currentIndexChanged.connect(update_conn_status_icon)
    db_combo_box.currentIndexChanged.connect(lambda: manager.results_manager.refresh_processes_view())
    
    QTimer.singleShot(100, update_conn_status_icon)

    toolbar_widget = WorksheetToolbar(manager)
    
    def on_limit_change(text):
        if text.lower() == "no limit":
            tab_content.current_limit = 0
        else:
            try:
                tab_content.current_limit = int(text)
            except ValueError:
                tab_content.current_limit = 0

        tab_content.current_page = 1
        tab_content.current_offset = 0
        page_label_widget = tab_content.findChild(QLabel, "page_label")
        if page_label_widget:
            page_label_widget.setText("Page 1")

        # Sync to Results View Label
        rows_info_label = tab_content.findChild(QLabel, "rows_info_label")
        if rows_info_label:
            limit = tab_content.current_limit
            offset = tab_content.current_offset
            if limit > 0:
                rows_info_label.setText(f"Limit: {limit} | Offset: {offset}")
            else:
                rows_info_label.setText("No Limit")
                
    toolbar_widget.limit_changed.connect(on_limit_change)
    layout.addWidget(toolbar_widget)
    layout.setStretchFactor(toolbar_widget, 0)

    main_vertical_splitter = QSplitter(Qt.Orientation.Vertical)
    main_vertical_splitter.setObjectName("tab_vertical_splitter")
    main_vertical_splitter.setHandleWidth(0)
    layout.addWidget(main_vertical_splitter)
    layout.setStretchFactor(main_vertical_splitter, 1)

    editor_container = QWidget()
    editor_container.setMinimumHeight(30)
    editor_layout = QVBoxLayout(editor_container)
    editor_layout.setContentsMargins(0, 0, 0, 0)
    editor_layout.setSpacing(0)

    editor_tabs = [
        ("Query", 120, 0),
        ("Query History", 120, 1),
        ("Test Case", 120, 2)
    ]
    editor_header = NavigationHeader("editorHeader", editor_tabs)
    editor_layout.addWidget(editor_header)

    editor_stack = QStackedWidget()
    editor_stack.setObjectName("editor_stack")

    text_edit = CodeEditor()
    text_edit.setPlaceholderText("Write your SQL query here...")
    text_edit.setObjectName("query_editor")
    text_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    text_edit.customContextMenuRequested.connect(lambda pos, editor=text_edit: manager.show_editor_context_menu(pos, editor))
    editor_stack.addWidget(text_edit)

    _sql_engine = CompletionEngine()
    text_edit.set_engine(_sql_engine)
    tab_content._sql_engine = _sql_engine

    history_widget = QSplitter(Qt.Orientation.Horizontal)
    history_widget.setHandleWidth(0)
    history_list_view = QTreeView()
    history_list_view.setObjectName("history_list_view")
    history_list_view.setHeaderHidden(True)
    history_list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    history_list_view.setRootIsDecorated(False)
    history_list_view.setAlternatingRowColors(True)
    history_list_view.setIndentation(0)
    history_list_view.setIndentation(0)

    history_details_group = QGroupBox("Query Details")
    history_details_layout = QVBoxLayout(history_details_group)
    history_details_view = QTextEdit()
    history_details_view.setObjectName("history_details_view")
    history_details_view.setReadOnly(True)
    history_details_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
    history_details_view.setFont(QFont("Consolas", 10))
    history_details_view.setFont(QFont("Consolas", 10))
    history_details_layout.addWidget(history_details_view)

    history_action_container = QWidget()
    history_action_container.setObjectName("historyActionContainer")
    history_button_layout = QHBoxLayout(history_action_container)
    history_button_layout.setContentsMargins(0, 8, 0, 0)
    history_button_layout.setSpacing(8)

    copy_history_btn = SecondaryButton(qta.icon("fa5s.copy", color="#555555"), "Copy")
    copy_to_edit_btn = SecondaryButton(qta.icon("fa5s.external-link-alt", color="#555555"), "Copy to Editor")
    remove_history_btn = SecondaryButton("Remove")
    remove_all_history_btn = SecondaryButton("Remove All")
    copy_history_btn.setMinimumWidth(78)
    copy_to_edit_btn.setMinimumWidth(132)
    remove_history_btn.setMinimumWidth(78)
    remove_all_history_btn.setMinimumWidth(98)

    history_button_layout.addStretch()
    history_button_layout.addWidget(copy_history_btn)
    history_button_layout.addWidget(copy_to_edit_btn)
    history_button_layout.addWidget(remove_history_btn)
    history_button_layout.addWidget(remove_all_history_btn)
    history_button_layout.addStretch()
    history_details_layout.addWidget(history_action_container)

    history_widget.addWidget(history_list_view)
    history_widget.addWidget(history_details_group)
    history_widget.setSizes([400, 400])
    editor_stack.addWidget(history_widget)

    test_cases_widget = TestCasesWidget()
    editor_stack.addWidget(test_cases_widget)

    editor_layout.addWidget(editor_stack)
    editor_layout.setStretchFactor(editor_stack, 1)
    main_vertical_splitter.addWidget(editor_container)

    def switch_editor_view(index):
        editor_stack.setCurrentIndex(index)
        if index == 1:
            manager.load_connection_history(tab_content)

    editor_header.tab_switched.connect(switch_editor_view)

    def _on_test_case_copy_to_editor(text):
        text_edit.setPlainText(text)
        btn = editor_header.get_button(0)
        if btn:
            btn.setChecked(True)
        switch_editor_view(0)

    test_cases_widget.copy_to_editor_requested.connect(_on_test_case_copy_to_editor)

    def _refresh_engine(skip_slow=False):
        data = db_combo_box.currentData()
        text_edit._conn_data = data
        code = (data.get("code") or data.get("db_type") or "").upper() if data else ""
        # ServiceNow connections are slow to connect — skip autocomplete pre-fetch
        # during the startup timer so we don't auto-connect before the user acts.
        if not skip_slow or code not in ("SERVICENOW",):
            tab_content._sql_engine.refresh(data)
        if limit_combo := tab_content.findChild(QComboBox, "rows_limit_combo"):
            if code == "SERVICENOW":
                limit_combo.setCurrentText("1000")
            elif limit_combo.currentText() == "1000" and code != "SERVICENOW":
                limit_combo.setCurrentText("No Limit")

    db_combo_box.currentIndexChanged.connect(lambda: _refresh_engine(skip_slow=False))
    QTimer.singleShot(300, lambda: _refresh_engine(skip_slow=True))

    db_combo_box.currentIndexChanged.connect(
        lambda: editor_stack.currentIndex() == 1 and manager.load_connection_history(tab_content)
    )
    history_list_view.clicked.connect(lambda index: manager.display_history_details(index, tab_content))

    copy_history_btn.clicked.connect(lambda: manager.copy_history_query(tab_content))
    copy_to_edit_btn.clicked.connect(lambda: manager.copy_history_to_editor(tab_content))
    remove_history_btn.clicked.connect(lambda: manager.remove_selected_history(tab_content))
    remove_all_history_btn.clicked.connect(lambda: manager.remove_all_history_for_connection(tab_content))

    results_container = manager.results_manager.create_results_ui(tab_content)
    main_vertical_splitter.addWidget(results_container)

    main_vertical_splitter.setSizes([400, 400])
    main_vertical_splitter.setStretchFactor(0, 1)
    main_vertical_splitter.setStretchFactor(1, 1)

    tab_content.setLayout(layout)
    next_tab_number = manager._next_worksheet_tab_number()
    index = manager.tab_widget.addTab(tab_content, f"Worksheet {next_tab_number}")
    manager.tab_widget.setTabIcon(index, manager._get_worksheet_tab_icon())
    manager.tab_widget.setCurrentIndex(index)
    manager.renumber_tabs()
    manager.results_manager._initialize_processes_model(tab_content)
    return tab_content
