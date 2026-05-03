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
    QPushButton,
    QAbstractItemView,
    QButtonGroup,
    QTreeView,
    QGroupBox,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QFont, QIcon, QKeySequence
import qtawesome as qta
from widgets.worksheet.connections import get_connection_icon
from widgets.worksheet.code_editor import CodeEditor
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

    db_combo_box = QComboBox()
    db_combo_box.setObjectName("db_combo_box")
    _popup_view = db_combo_box.view()
    _popup_view.setMouseTracking(True)
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

    toolbar_widget = QWidget()

    toolbar_widget.setObjectName("tab_toolbar")
    toolbar_layout = QHBoxLayout(toolbar_widget)
    toolbar_layout.setContentsMargins(6, 3, 6, 3)
    toolbar_layout.setSpacing(6)

    btn_style = (
        "QToolButton, QPushButton, QComboBox { "
        "padding: 2px 8px; border: 1px solid #b9b9b9; "
        "background-color: #ffffff; border-radius: 4px; "
        "font-size: 9pt; color: #333333; "
        "} "
        "QToolButton:hover, QPushButton:hover, QComboBox:hover { "
        "background-color: #e8e8e8; border-color: #9c9c9c; "
        "} "
        "QToolButton:pressed, QPushButton:pressed, QComboBox:on { "
        "background-color: #dcdcdc; "
        "} "
        "QComboBox::drop-down { "
        "border: none; border-left: 1px solid #c6c6c6; "
        "width: 24px; "
        "border-top-right-radius: 4px; "
        "border-bottom-right-radius: 4px; "
        "} "
        "QComboBox::drop-down:hover { "
        "background-color: #dcdcdc; "
        "} "
        "QComboBox::down-arrow { "
        "image: url(assets/chevron-down.svg); "
        "width: 10px; height: 10px; "
        "} "
    )

    open_btn = QToolButton()
    open_btn.setDefaultAction(manager.open_file_action)
    open_btn.setIconSize(QSize(16, 16))
    open_btn.setFixedHeight(30)
    open_btn.setMinimumWidth(26)
    open_btn.setToolTip("Open SQL File")
    open_btn.setStyleSheet(btn_style)
    toolbar_layout.addWidget(open_btn)

    save_btn = QToolButton()
    save_btn.setDefaultAction(manager.save_as_action)
    save_btn.setIconSize(QSize(16, 16))
    save_btn.setFixedHeight(30)
    save_btn.setMinimumWidth(26)
    save_btn.setToolTip("Save SQL File")
    save_btn.setStyleSheet(btn_style)
    toolbar_layout.addWidget(save_btn)

    toolbar_layout.addWidget(manager.create_vertical_separator())

    exec_btn = QToolButton()
    exec_btn.setDefaultAction(manager.execute_action)
    exec_btn.setIconSize(QSize(16, 16))
    exec_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    exec_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
    exec_menu = QMenu(exec_btn)
    exec_menu.addAction(manager.execute_new_tab_action)
    exec_btn.setMenu(exec_menu)
    exec_btn.setFixedHeight(30)
    exec_btn.setStyleSheet(btn_style)
    toolbar_layout.addWidget(exec_btn)

    cancel_btn = QToolButton()
    cancel_btn.setDefaultAction(manager.cancel_action)
    cancel_btn.setIconSize(QSize(16, 16))
    cancel_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    cancel_btn.setFixedHeight(30)
    cancel_btn.setStyleSheet(btn_style)
    toolbar_layout.addWidget(cancel_btn)

    explain_combo = QComboBox()
    explain_combo.setFixedHeight(30)
    explain_combo.setFixedWidth(135)
    explain_combo.setStyleSheet(btn_style)
    explain_combo.addItem(QIcon("assets/explain_icon.png"), "Explain Analyze")
    explain_combo.addItem(QIcon("assets/explain_icon.png"), "Explain (Plan)")

    def on_explain_activated(index):
        if index == 0:
            manager.explain_query()
        else:
            manager.explain_plan_query()

    explain_combo.activated.connect(on_explain_activated)
    toolbar_layout.addWidget(explain_combo)

    edit_btn = QToolButton()
    edit_btn.setText("Edit")
    edit_btn.setIcon(qta.icon("fa5s.edit"))
    edit_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    edit_btn.setFixedHeight(30)
    edit_btn.setFixedWidth(85)
    edit_btn.setStyleSheet(
        btn_style
        + """
            QToolButton::menu-indicator {
                border-left: 1px solid #dddfe2;
                width: 20px;
                image: url(assets/chevron-down.svg);
                subcontrol-origin: padding;
                subcontrol-position: right center;
                margin-left: 4px;
            }
        """
    )
    edit_btn.setToolTip("Edit Operations")
    edit_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    edit_menu = QMenu(manager)
    edit_menu.setStyleSheet(
        """
            QMenu { background-color: #ffffff; border: 1px solid #b9b9b9; }
            QMenu::item { padding: 4px 20px 4px 4px; spacing: 4px; min-width: 250px; }
            QMenu::item:selected { background-color: #e8e8e8; color: #333333; }
            QMenu::icon { padding: 4px; }
            QMenu::separator { height: 1px; background: #eeeeee; margin: 2px 0px; }
        """
    )
    def add_menu_action(text, shortcut=None, icon=None, func=None):
        action = QAction(text, manager)
        if icon:
            if isinstance(icon, str):
                action.setIcon(QIcon(icon))
            else:
                action.setIcon(icon)
            action.setIconVisibleInMenu(True)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if func:
            action.triggered.connect(func)
        edit_menu.addAction(action)
        return action

    edit_menu.addAction(manager.main_window.undo_action)
    edit_menu.addAction(manager.main_window.redo_action)
    edit_menu.addSeparator()
    edit_menu.addAction(manager.main_window.cut_action)
    edit_menu.addAction(manager.main_window.copy_action)
    edit_menu.addAction(manager.main_window.paste_action)
    edit_menu.addAction(manager.main_window.select_all_action)
    edit_menu.addSeparator()
    edit_menu.addAction(manager.main_window.find_action)
    edit_menu.addAction(manager.main_window.replace_action)
    edit_menu.addAction(manager.main_window.goto_line_action)
    edit_menu.addSeparator()
    edit_menu.addAction(manager.main_window.comment_block_action)
    edit_menu.addAction(manager.main_window.uncomment_block_action)
    edit_menu.addAction(manager.main_window.upper_case_action)
    edit_menu.addAction(manager.main_window.lower_case_action)
    edit_menu.addAction(manager.main_window.initial_caps_action)
    edit_menu.addSeparator()
    edit_menu.addAction(manager.main_window.clear_all_action)
    edit_menu.addAction(manager.main_window.format_sql_action)

    edit_btn.setMenu(edit_menu)
    toolbar_layout.addWidget(edit_btn)

    toolbar_layout.addWidget(manager.create_vertical_separator())
    rows_label = QLabel("Limit:")
    toolbar_layout.addWidget(rows_label)

    rows_limit_combo = QComboBox()
    rows_limit_combo.setObjectName("rows_limit_combo")
    rows_limit_combo.setEditable(False)
    rows_limit_combo.addItems(["No Limit", "100", "500", "1000"])
    rows_limit_combo.setCurrentText("No Limit")
    rows_limit_combo.setFixedWidth(90)
    rows_limit_combo.setFixedHeight(30)
    rows_limit_combo.setStyleSheet(btn_style)

    def on_limit_change():
        text = rows_limit_combo.currentText().strip()
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

    rows_limit_combo.currentIndexChanged.connect(on_limit_change)
    toolbar_layout.addWidget(rows_limit_combo)

    toolbar_layout.addWidget(manager.create_vertical_separator())
    toolbar_layout.addStretch()
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

    editor_header = QWidget()
    editor_header.setObjectName("editorHeader")
    editor_header_layout = QHBoxLayout(editor_header)
    editor_header_layout.setContentsMargins(6, 3, 6, 1)
    editor_header_layout.setSpacing(4)

    query_view_btn = QPushButton("Query")
    history_view_btn = QPushButton("Query History")
    query_view_btn.setObjectName("query_view_btn")
    history_view_btn.setObjectName("history_view_btn")
    query_view_btn.setMinimumWidth(120)
    history_view_btn.setMinimumWidth(120)
    query_view_btn.setCheckable(True)
    history_view_btn.setCheckable(True)
    query_view_btn.setChecked(True)

    editor_header_layout.addWidget(query_view_btn)
    editor_header_layout.addWidget(history_view_btn)
    editor_header_layout.addStretch()
    editor_layout.addWidget(editor_header)

    editor_button_group = QButtonGroup(manager)
    editor_button_group.setExclusive(True)
    editor_button_group.addButton(query_view_btn, 0)
    editor_button_group.addButton(history_view_btn, 1)

    editor_stack = QStackedWidget()
    editor_stack.setObjectName("editor_stack")

    text_edit = CodeEditor()
    text_edit.setPlaceholderText("Write your SQL query here...")
    text_edit.setObjectName("query_editor")
    text_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    text_edit.customContextMenuRequested.connect(lambda pos, editor=text_edit: manager.show_editor_context_menu(pos, editor))
    editor_stack.addWidget(text_edit)

    history_widget = QSplitter(Qt.Orientation.Horizontal)
    history_widget.setHandleWidth(0)
    history_list_view = QTreeView()
    history_list_view.setObjectName("history_list_view")
    history_list_view.setHeaderHidden(True)
    history_list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    history_list_view.setRootIsDecorated(False)
    history_list_view.setAlternatingRowColors(True)
    history_list_view.setIndentation(0)
    history_list_view.setStyleSheet(
        """
            QTreeView {
                border: 1px solid #d8dce2;
                border-radius: 6px;
                background: #ffffff;
                alternate-background-color: #f7f9fc;
                padding: 4px;
            }
            QTreeView::item {
                padding: 6px 8px;
                border-bottom: 1px solid #f0f2f5;
            }
            QTreeView::item:selected {
                background: #eaf2ff;
                color: #1f2937;
            }
        """
    )

    history_details_group = QGroupBox("Query Details")
    history_details_layout = QVBoxLayout(history_details_group)
    history_details_view = QTextEdit()
    history_details_view.setObjectName("history_details_view")
    history_details_view.setReadOnly(True)
    history_details_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
    history_details_view.setFont(QFont("Consolas", 10))
    history_details_view.setStyleSheet(
        """
            QTextEdit {
                border: 1px solid #d8dce2;
                border-radius: 6px;
                background: #ffffff;
                padding: 8px;
            }
        """
    )
    history_details_layout.addWidget(history_details_view)

    history_button_layout = QHBoxLayout()
    history_button_layout.setContentsMargins(0, 8, 0, 0)
    history_button_layout.setSpacing(8)
    history_action_btn_style = """
        QPushButton {
            min-height: 26px;
            padding: 2px 10px;
            border: 1px solid #cfd6df;
            border-radius: 6px;
            background: #ffffff;
            color: #1f2937;
            font-size: 9pt;
        }
        QPushButton:hover {
            background: #f4f7fb;
            border-color: #b8c2cf;
        }
        QPushButton:pressed {
            background: #e9eef5;
        }
    """
    copy_history_btn = QPushButton(qta.icon("fa5s.copy", color="#555555"), "Copy")
    copy_to_edit_btn = QPushButton(qta.icon("fa5s.external-link-alt", color="#555555"), "Copy to Editor")
    remove_history_btn = QPushButton("Remove")
    remove_all_history_btn = QPushButton("Remove All")
    copy_history_btn.setMinimumWidth(78)
    copy_to_edit_btn.setMinimumWidth(132)
    remove_history_btn.setMinimumWidth(78)
    remove_all_history_btn.setMinimumWidth(98)
    copy_history_btn.setStyleSheet(history_action_btn_style)
    copy_to_edit_btn.setStyleSheet(history_action_btn_style)
    remove_history_btn.setStyleSheet(history_action_btn_style)
    remove_all_history_btn.setStyleSheet(history_action_btn_style)

    history_button_layout.addStretch()
    history_button_layout.addWidget(copy_history_btn)
    history_button_layout.addWidget(copy_to_edit_btn)
    history_button_layout.addWidget(remove_history_btn)
    history_button_layout.addWidget(remove_all_history_btn)
    history_button_layout.addStretch()
    history_details_layout.addLayout(history_button_layout)

    history_widget.addWidget(history_list_view)
    history_widget.addWidget(history_details_group)
    history_widget.setSizes([400, 400])
    editor_stack.addWidget(history_widget)

    editor_layout.addWidget(editor_stack)
    editor_layout.setStretchFactor(editor_stack, 1)
    main_vertical_splitter.addWidget(editor_container)

    def switch_editor_view(index):
        editor_stack.setCurrentIndex(index)
        if index == 1:
            manager.load_connection_history(tab_content)

    query_view_btn.clicked.connect(lambda: switch_editor_view(0))
    history_view_btn.clicked.connect(lambda: switch_editor_view(1))

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
