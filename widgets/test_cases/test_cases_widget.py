from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QScrollArea,
    QGroupBox, QLabel, QTextEdit, QPushButton, QHBoxLayout,
    QApplication, QSplitter, QListWidget
)
from PySide6.QtCore import Qt, Signal
import qtawesome as qta

from widgets.test_cases.data.table import TABLE_COMMANDS
from widgets.test_cases.data.view import VIEW_COMMANDS
from widgets.test_cases.data.complex_queries import COMPLEX_QUERIES
from widgets.test_cases.data.function import FUNCTION_COMMANDS
from widgets.test_cases.data.rls import RLS_COMMANDS

class TestCasesWidget(QWidget):
    copy_to_editor_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_data()
        self.init_ui()

    def init_data(self):
        self.test_data = {
            "Tables": TABLE_COMMANDS,
            "Views": VIEW_COMMANDS,
            "Complex Queries": COMPLEX_QUERIES,
            "Functions": FUNCTION_COMMANDS,
            "Row-Level Security": RLS_COMMANDS
        }

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # Left side: Category List
        self.category_list = QListWidget()
        self.category_list.addItems(self.test_data.keys())
        self.category_list.setFixedWidth(150)
        self.category_list.setStyleSheet(
            """
            QListWidget {
                border: 1px solid #d8dce2;
                border-radius: 4px;
                background: #ffffff;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f2f5;
            }
            QListWidget::item:selected {
                background: #eaf2ff;
                color: #1f2937;
                font-weight: bold;
            }
            """
        )
        
        # Right side: Content Tabs
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs)

        # Command Tab
        self.command_tab = QWidget()
        self.command_layout = QVBoxLayout(self.command_tab)
        self.command_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.command_layout.addWidget(self.scroll_area)
        
        self.tabs.addTab(self.command_tab, "Command")

        # Dialog Box Tab
        self.dialog_tab = QWidget()
        self.init_dialog_tab()
        self.tabs.addTab(self.dialog_tab, "Dialog Box")

        splitter.addWidget(self.category_list)
        splitter.addWidget(self.right_panel)
        splitter.setSizes([150, 600])

        self.category_list.currentItemChanged.connect(self.on_category_changed)
        
        # Select first category by default
        if self.category_list.count() > 0:
            self.category_list.setCurrentRow(0)

    def on_category_changed(self, current, previous):
        if not current:
            return
        
        category = current.text()
        self.populate_commands(category)

    def populate_commands(self, category):
        # Create a new container to replace the old one in scroll_area
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(10)

        commands = self.test_data.get(category, [])

        action_btn_style = """
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

        for cmd in commands:
            group = QGroupBox(cmd["title"])
            group_layout = QVBoxLayout(group)

            desc_label = QLabel(cmd["description"])
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #555555; font-style: italic;")
            group_layout.addWidget(desc_label)

            text_edit = QTextEdit()
            text_edit.setPlainText(cmd["sql"])
            text_edit.setReadOnly(True)
            text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            
            line_count = cmd["sql"].count('\n') + 1
            full_height = line_count * 18 + 16
            
            show_more_btn = None
            if line_count > 6:
                collapsed_height = 6 * 18 + 16
                text_edit.setFixedHeight(collapsed_height)
                
                show_more_btn = QPushButton("Show More")
                show_more_btn.setStyleSheet("color: #0052cc; border: none; text-align: left; font-size: 9pt; background: transparent; margin: 0; padding: 0;")
                show_more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                
                def make_toggle(te=text_edit, btn=show_more_btn, f_h=full_height, c_h=collapsed_height):
                    def toggle(checked=False):
                        if btn.text() == "Show More":
                            te.setFixedHeight(f_h)
                            btn.setText("Show Less")
                        else:
                            te.setFixedHeight(c_h)
                            btn.setText("Show More")
                    return toggle
                
                show_more_btn.clicked.connect(make_toggle())
            else:
                text_edit.setFixedHeight(full_height)
                
            text_edit.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 4px; font-family: Consolas, monospace;")
            group_layout.addWidget(text_edit)
            
            if show_more_btn:
                group_layout.addWidget(show_more_btn)

            btn_layout = QHBoxLayout()
            copy_btn = QPushButton("Copy")
            copy_btn.setIcon(qta.icon("fa5s.copy", color="#555555"))
            copy_btn.setStyleSheet(action_btn_style)
            copy_btn.setMinimumWidth(78)
            copy_btn.clicked.connect(lambda checked=False, text=cmd["sql"]: self.copy_to_clipboard(text))
            
            copy_editor_btn = QPushButton("Copy to Editor")
            copy_editor_btn.setIcon(qta.icon("fa5s.external-link-alt", color="#555555"))
            copy_editor_btn.setStyleSheet(action_btn_style)
            copy_editor_btn.setMinimumWidth(132)
            copy_editor_btn.clicked.connect(lambda checked=False, text=cmd["sql"]: self.copy_to_editor_requested.emit(text))
            
            btn_layout.addStretch()
            btn_layout.addWidget(copy_btn)
            btn_layout.addWidget(copy_editor_btn)
            group_layout.addLayout(btn_layout)

            container_layout.addWidget(group)

        container_layout.addStretch()
        self.scroll_area.setWidget(container)

    def init_dialog_tab(self):
        layout = QVBoxLayout(self.dialog_tab)
        label = QLabel("Dialog Box Feature - Coming Soon")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

    def copy_to_clipboard(self, text):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
