import os
import qtawesome as qta

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QFont, QIcon, QMovie
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from widgets.results_view.explain import create_explain_view
from widgets.results_view.messages import create_message_view
from widgets.results_view.notifications import create_notification_view
from widgets.results_view.output_tabs import create_output_tabs_view
from widgets.results_view.processes import create_processes_view


def create_results_ui(manager, tab_content):
    tab_content._results_manager = manager
    results_container = QWidget()
    results_container.setMinimumHeight(30)
    results_layout = QVBoxLayout(results_container)
    results_layout.setContentsMargins(0, 0, 0, 0)
    results_layout.setSpacing(0)

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
    add_row_btn.setIcon(qta.icon("ri.play-list-add-fill", color="#555555"))
    add_row_btn.setIconSize(QSize(16, 16))
    add_row_btn.setFixedSize(30, 30)
    add_row_btn.setToolTip("Add new row")
    add_row_btn.setObjectName("add_row_btn")
    add_row_btn.setStyleSheet(btn_style_bottom)
    add_row_btn.clicked.connect(manager.add_empty_row)

    save_row_btn = QPushButton()
    save_row_btn.setIcon(qta.icon("fa5s.save", color="#555555"))
    save_row_btn.setIconSize(QSize(16, 16))
    save_row_btn.setFixedSize(30, 30)
    save_row_btn.setToolTip("Save new row")
    save_row_btn.setObjectName("save_row_btn")
    save_row_btn.setStyleSheet(btn_style_bottom)
    results_info_layout.addWidget(add_row_btn)
    results_info_layout.addWidget(save_row_btn)

    save_row_btn.clicked.connect(manager.save_new_row)

    copy_btn = QToolButton()
    copy_btn.setIcon(qta.icon("fa5s.copy", color="#555555"))
    copy_btn.setIconSize(QSize(16, 16))
    copy_btn.setFixedSize(30, 30)
    copy_btn.setToolTip("Copy selected cells (Ctrl+C)")
    copy_btn.setStyleSheet(btn_style_bottom)

    paste_btn = QToolButton()
    paste_btn.setIcon(qta.icon("fa5s.paste", color="#555555"))
    paste_btn.setIconSize(QSize(16, 16))
    paste_btn.setFixedSize(30, 30)
    paste_btn.setToolTip("Paste to editor")
    paste_btn.setStyleSheet(btn_style_bottom)
    paste_btn.clicked.connect(manager.paste_to_editor)

    delete_row_btn = QPushButton()
    delete_row_btn.setIcon(qta.icon("fa5s.trash-alt", color="#dc3545"))
    delete_row_btn.setIconSize(QSize(16, 16))
    delete_row_btn.setFixedSize(30, 30)
    delete_row_btn.setToolTip("Delete selected row(s)")
    delete_row_btn.setObjectName("delete_row_btn")
    delete_row_btn.setStyleSheet(btn_style_bottom)

    delete_row_btn.clicked.connect(manager.delete_selected_row)

    results_info_layout.addWidget(delete_row_btn)
    results_info_layout.addWidget(copy_btn)
    results_info_layout.addWidget(paste_btn)

    download_btn = QPushButton()
    download_btn.setIcon(qta.icon("fa5s.file-download", color="#555555"))
    download_btn.setIconSize(QSize(16, 16))
    download_btn.setFixedSize(30, 30)
    download_btn.setToolTip("Download query result")
    download_btn.setStyleSheet(btn_style_bottom)
    download_btn.clicked.connect(lambda: manager.download_result(tab_content))
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
    search_box.hide()
    search_box.installEventFilter(manager)

    table_search_btn = QToolButton()
    table_search_btn.setObjectName("table_search_btn")
    table_search_btn.setIcon(qta.icon("fa5s.search", color="#555555"))
    table_search_btn.setFixedSize(30, 30)
    table_search_btn.setToolTip("Search in Results")
    table_search_btn.setStyleSheet(
        """
            QToolButton {
                border: 1px solid #b9b9b9;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QToolButton:hover {
                background-color: #e8e8e8;
                border: 1px solid #9c9c9c;
            }
        """
    )
    table_search_btn.clicked.connect(manager.toggle_table_search)

    search_debounce_timer = QTimer()
    search_debounce_timer.setInterval(300)
    search_debounce_timer.setSingleShot(True)

    def trigger_filter():
        current_table = manager._get_result_table_for_tab(tab_content)
        if current_table:
            current_model = current_table.model()
            if hasattr(current_model, "setFilterFixedString"):
                current_model.setFilterFixedString(search_box.text())

    def on_search_text_changed(text):
        search_debounce_timer.stop()
        search_debounce_timer.start()

    search_debounce_timer.timeout.connect(trigger_filter)
    search_box.textChanged.connect(on_search_text_changed)
    results_info_layout.addWidget(search_box)
    results_info_layout.addWidget(table_search_btn)

    results_info_bar.hide()
    results_info_layout.addStretch()

    rows_info_label = QLabel("Showing Rows")
    rows_info_label.setObjectName("rows_info_label")
    font = QFont()
    font.setBold(True)
    rows_info_label.setFont(font)
    results_info_layout.addWidget(rows_info_label)

    rows_setting_btn = QToolButton()
    rows_setting_btn.setIcon(qta.icon("fa5s.list-ul", color="#555555"))
    rows_setting_btn.setIconSize(QSize(16, 16))
    rows_setting_btn.setFixedSize(28, 28)
    rows_setting_btn.setToolTip("Edit Limit/Offset")
    rows_setting_btn.setStyleSheet(btn_style_bottom)
    rows_setting_btn.clicked.connect(lambda: manager.open_limit_offset_dialog(tab_content))
    results_info_layout.addWidget(rows_setting_btn)

    arrow_font = QFont("Segoe UI", 16, QFont.Weight.Bold)

    nav_btn_style = (
        "QPushButton { "
        "border: 1px solid #b9b9b9; "
        "border-radius: 4px; "
        "background-color: #ffffff; "
        "color: #333333; "
        "padding: 0px; "
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
        "}"
    )

    prev_btn = QPushButton("◀")
    prev_btn.setFixedSize(30, 28)
    prev_btn.setFont(arrow_font)
    prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    prev_btn.setEnabled(True)
    prev_btn.setObjectName("prev_btn")
    prev_btn.setStyleSheet(nav_btn_style)

    page_label = QLabel("Page 1")
    page_label.setMinimumWidth(60)
    page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    page_label.setFont(QFont("Segoe UI", 9))
    page_label.setObjectName("page_label")

    next_btn = QPushButton("▶")
    next_btn.setFixedSize(30, 28)
    next_btn.setFont(arrow_font)
    next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    next_btn.setEnabled(True)
    next_btn.setObjectName("next_btn")
    next_btn.setStyleSheet(nav_btn_style)

    results_info_layout.addWidget(prev_btn)
    results_info_layout.addWidget(page_label)
    results_info_layout.addWidget(next_btn)

    results_layout.addWidget(results_info_bar)

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
    success_filter_btn = QPushButton("Successful (0)")
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

    all_filter_btn.clicked.connect(lambda: manager._set_process_filter(tab_content, "ALL"))
    running_filter_btn.clicked.connect(lambda: manager._set_process_filter(tab_content, "RUNNING"))
    success_filter_btn.clicked.connect(lambda: manager._set_process_filter(tab_content, "SUCCESSFUL"))
    warning_filter_btn.clicked.connect(lambda: manager._set_process_filter(tab_content, "WARNING"))
    error_filter_btn.clicked.connect(lambda: manager._set_process_filter(tab_content, "ERROR"))

    tab_content.process_filter_buttons = {
        "ALL": all_filter_btn,
        "RUNNING": running_filter_btn,
        "SUCCESSFUL": success_filter_btn,
        "WARNING": warning_filter_btn,
        "ERROR": error_filter_btn,
    }

    process_filter_layout.addStretch()
    
    # Search Field
    search_edit = QLineEdit()
    search_edit.setPlaceholderText("Search processes...")
    search_edit.setFixedWidth(150)
    search_edit.textChanged.connect(lambda text: manager._filter_processes_table(tab_content, text))
    process_filter_layout.addWidget(QLabel("Search:"))
    process_filter_layout.addWidget(search_edit)
    
    # View Log Button
    view_log_btn = QPushButton(qta.icon("fa5s.file-alt"), "View Log")
    view_log_btn.clicked.connect(lambda: manager._handle_view_log(tab_content))
    process_filter_layout.addWidget(view_log_btn)


    refresh_now_btn = QPushButton("Refresh")
    refresh_now_btn.setObjectName("process_refresh_now_btn")
    refresh_now_btn.setStyleSheet(filter_btn_style)
    refresh_now_btn.setFixedHeight(28)
    refresh_now_btn.setMinimumWidth(76)
    refresh_now_btn.clicked.connect(manager.refresh_processes_view)
    process_filter_layout.addWidget(refresh_now_btn)

    process_filter_bar.setStyleSheet("background: #ECEFF3; border-bottom: 1px solid #C9CFD8;")
    process_filter_bar.hide()
    results_layout.addWidget(process_filter_bar)

    process_info_bar = QWidget()
    process_info_bar.setObjectName("processInfoBar")
    process_info_layout = QHBoxLayout(process_info_bar)
    process_info_layout.setContentsMargins(8, 3, 8, 3)
    process_info_layout.setSpacing(20)

    process_summary_label = QLabel("")
    process_summary_label.setObjectName("process_summary_label")
    process_selection_label = QLabel("")
    process_selection_label.setObjectName("process_selection_label")

    process_info_bar.setStyleSheet("background: transparent; border: none;")
    process_info_bar.hide()
    results_layout.addWidget(process_info_bar)

    tab_content.process_filter_bar = process_filter_bar

    def update_page_ui(tab):
        page_label.setText(f"Page {tab.current_page}")

        prev_btn.setEnabled(tab.current_page > 1)

        limit = getattr(tab, "current_limit", 0)
        offset = getattr(tab, "current_offset", 0)

        if limit and limit > 0:
            rows_info_label.setText(f"Limit: {limit} | Offset: {offset}")
        else:
            rows_info_label.setText("No Limit")

    def go_prev():
        tab = tab_content
        if not tab or tab.current_page <= 1:
            return
        tab.current_page -= 1
        tab.current_offset = (tab.current_page - 1) * tab.current_limit
        update_page_ui(tab)
        manager.main_window.worksheet_manager.execute_query(preserve_pagination=True)

    def go_next():
        tab = tab_content
        if not tab.has_more_pages:
            return
        tab.current_page += 1
        tab.current_offset = (tab.current_page - 1) * tab.current_limit
        update_page_ui(tab)
        manager.main_window.worksheet_manager.execute_query(preserve_pagination=True)

    prev_btn.clicked.connect(go_prev)
    next_btn.clicked.connect(go_next)

    results_button_group = QButtonGroup(results_container)
    results_button_group.setExclusive(True)
    results_button_group.addButton(output_btn, 0)
    results_button_group.addButton(message_btn, 1)
    results_button_group.addButton(notification_btn, 2)
    results_button_group.addButton(process_btn, 3)
    results_button_group.addButton(explain_btn, 5)

    results_stack = QStackedWidget()
    results_stack.setObjectName("results_stacked_widget")

    output_tabs = create_output_tabs_view(manager, tab_content)
    results_stack.addWidget(output_tabs)

    copy_btn.clicked.connect(manager.copy_current_result_table)

    results_stack.addWidget(create_message_view(manager, tab_content))

    results_stack.addWidget(create_notification_view())

    processes_view = create_processes_view(manager, tab_content)
    manager._initialize_processes_model(tab_content)

    results_stack.addWidget(processes_view)

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

    explain_visualizer = create_explain_view()
    results_stack.addWidget(explain_visualizer)

    placeholder_widget = QWidget()
    placeholder_layout = QVBoxLayout(placeholder_widget)
    placeholder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    placeholder_content = QWidget()
    placeholder_content_layout = QHBoxLayout(placeholder_content)
    placeholder_content_layout.setSpacing(10)
    placeholder_content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    info_icon_label = QLabel()
    info_icon_path = "assets/information.svg"
    if os.path.exists(info_icon_path):
        info_icon_label.setPixmap(QIcon(info_icon_path).pixmap(20, 20))
    else:
        # Fallback if svg not found, maybe just a text or circle
        info_icon_label.setText("ⓘ")
        info_icon_label.setStyleSheet("font-weight: bold; font-size: 14pt; color: #555;")

    placeholder_message = QLabel("No data output. Execute a query to get output.")
    placeholder_message.setStyleSheet("color: #555; font-size: 10pt;")
    
    placeholder_content_layout.addWidget(info_icon_label)
    placeholder_content_layout.addWidget(placeholder_message)
    
    placeholder_layout.addWidget(placeholder_content)
    results_stack.addWidget(placeholder_widget)

    results_stack.setCurrentIndex(6)

    results_layout.addWidget(results_stack)
    results_layout.setStretchFactor(results_stack, 1)

    tab_status_label = QLabel("Ready")
    tab_status_label.setObjectName("tab_status_label")
    results_layout.addWidget(tab_status_label)
    results_layout.setStretchFactor(tab_status_label, 0)

    def switch_results_view(index):
        results_stack.setCurrentIndex(index)

        if index == 0:
            if results_stack.widget(0).findChild(QTableView, "results_table"):
              results_info_bar.show()
            else:
              results_info_bar.hide()
            process_info_bar.hide()
            process_filter_bar.hide()
        elif index == 3:
            results_info_bar.hide()
            process_filter_bar.show()
            process_info_bar.hide()
            manager.refresh_processes_view()
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
