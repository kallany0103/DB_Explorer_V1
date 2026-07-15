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
import PySide6.QtWidgets as QtWidgets

from widgets.results_view.explain import create_explain_view
from widgets.results_view.messages import create_message_view
from widgets.results_view.notifications import create_notification_view
from widgets.results_view.output_tabs import create_output_tabs_view
from widgets.results_view.processes import create_processes_view
from ui.components import IconButton, SearchBox
from ui.toolbars import NavigationHeader


def create_results_ui(manager, tab_content):
    tab_content._results_manager = manager
    results_container = QWidget()
    results_container.setMinimumHeight(30)
    results_layout = QVBoxLayout(results_container)
    results_layout.setContentsMargins(0, 0, 0, 0)
    results_layout.setSpacing(0)

    results_tabs = [
        ("Output", 100, 0),
        ("Messages", 100, 1),
        ("Notifications", 120, 2),
        ("Processes", 100, 3),
        ("Explain", 100, 5)
    ]
    results_header = NavigationHeader("resultsHeader", results_tabs)
    results_layout.addWidget(results_header)

    from ui.toolbars import ResultsInfoToolbar, ProcessFilterBar
    results_info_bar = ResultsInfoToolbar(manager, tab_content)
    results_layout.addWidget(results_info_bar)

    process_filter_bar = ProcessFilterBar(manager, tab_content)
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





    results_stack = QStackedWidget()
    results_stack.setObjectName("results_stacked_widget")

    output_tabs = create_output_tabs_view(manager, tab_content)
    results_stack.addWidget(output_tabs)

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

    results_header.tab_switched.connect(switch_results_view)

    return results_container
