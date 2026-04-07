import os

# from PyQt6.QtWidgets import (
#     QVBoxLayout, QWidget, QHBoxLayout, QLabel, QLineEdit, QToolButton,
#     QSplitter, QTreeView, QFrame, QAbstractItemView, QHeaderView
# )
# from PyQt6.QtGui import QIcon, QStandardItemModel
# from PyQt6.QtCore import Qt, QSize, QSortFilterProxyModel

from PySide6.QtWidgets import (
    QVBoxLayout, QWidget, QHBoxLayout, QLabel, QLineEdit, QToolButton,
    QSplitter, QTreeView, QFrame, QAbstractItemView, QHeaderView
)
from PySide6.QtGui import QIcon, QStandardItemModel
from PySide6.QtCore import Qt, QSize, QSortFilterProxyModel


class ConnectionUI:
    def __init__(self, manager):
        self.manager = manager

    def init_ui(self):
        layout = QVBoxLayout(self.manager)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        object_explorer_header = QWidget()
        object_explorer_header.setFixedHeight(36)
        object_explorer_header.setObjectName("objectExplorerHeader")
        object_explorer_header.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        object_explorer_header.setStyleSheet("""
            #objectExplorerHeader {
                background-color: #9FA6AF;
                border-bottom: 1px solid #8B929B;
            }
        """)
        object_explorer_header_layout = QHBoxLayout(object_explorer_header)
        object_explorer_header_layout.setContentsMargins(8, 4, 8, 4)
        object_explorer_header_layout.setSpacing(10)

        object_explorer_label = QLabel("Object Explorer")
        object_explorer_label.setObjectName("objectExplorerLabel")
        object_explorer_label.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        object_explorer_label.setStyleSheet("color: white; font-weight: bold; font-size: 10pt;")
        object_explorer_header_layout.addWidget(object_explorer_label)

        self.manager.explorer_search_container = QWidget()
        self.manager.explorer_search_layout = QHBoxLayout(self.manager.explorer_search_container)
        self.manager.explorer_search_layout.setContentsMargins(0, 0, 0, 0)
        self.manager.explorer_search_layout.setSpacing(0)

        self.manager.explorer_search_box = QLineEdit()
        self.manager.explorer_search_box.setPlaceholderText("Filter...")
        self.manager.explorer_search_box.setFixedHeight(24)
        self.manager.explorer_search_box.setObjectName("explorer_search_box")
        self.manager.explorer_search_box.setMinimumWidth(120)
        self.manager.explorer_search_box.hide()

        search_icon_path = "assets/search.svg"
        if os.path.exists(search_icon_path):
            self.manager.explorer_search_box.addAction(QIcon(search_icon_path), QLineEdit.ActionPosition.LeadingPosition)

        self.manager.explorer_search_box.setStyleSheet("""
            QLineEdit {
                border: 1px solid #A9A9A9;
                border-radius: 4px;
                padding-left: 2px;
                background-color: #ffffff;
                font-size: 9pt;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
                background-color: #ffffff;
            }
        """)
        self.manager.explorer_search_box.textChanged.connect(self.manager.filter_object_explorer)
        self.manager.explorer_search_box.installEventFilter(self.manager)


        self.manager.explorer_search_btn = QToolButton()
        self.manager.explorer_search_btn.setIcon(QIcon(search_icon_path if os.path.exists(search_icon_path) else ""))
        self.manager.explorer_search_btn.setFixedSize(24, 24)
        self.manager.explorer_search_btn.setIconSize(QSize(16, 16))
        self.manager.explorer_search_btn.setToolTip("Search Connections")
        self.manager.explorer_search_btn.setStyleSheet("""
            QToolButton {
                border: none;
                border-radius: 4px;
                background-color: transparent;
            }
            QToolButton:hover {
                background-color: #C9CFD8;
            }
            QToolButton:pressed {
                background-color: #B8BEC6;
            }
        """)
        self.manager.explorer_search_btn.clicked.connect(self.manager.toggle_explorer_search)

        self.manager.explorer_search_layout.addWidget(self.manager.explorer_search_box)
        self.manager.explorer_search_layout.addWidget(self.manager.explorer_search_btn)

                         # New Connection Type
        self.add_new_type_btn = QToolButton()
        self.add_new_type_btn.setFixedSize(24, 24)
        self.add_new_type_btn.setIconSize(QSize(16, 16))
        self.add_new_type_btn.setToolTip("Add New Connection")
        self.add_new_type_btn.setIcon(QIcon("assets/plus.svg"))
        self.add_new_type_btn.setStyleSheet("""
            QToolButton {
                border: none;
                border-radius: 4px;
                background-color: transparent;
            }
            QToolButton:hover {
                background-color: #C9CFD8;
            }
            QToolButton:pressed {
                background-color: #B8BEC6;
            }
        """)
        self.add_new_type_btn.clicked.connect(self.manager.add_connection_flow)

        object_explorer_header_layout.addStretch()
        object_explorer_header_layout.addWidget(self.manager.explorer_search_container)
        object_explorer_header_layout.addWidget(self.add_new_type_btn)

        self.manager.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self.manager.vertical_splitter.setHandleWidth(0)
        self.manager.vertical_splitter.setStyleSheet("QSplitter { border: none; margin: 0; padding: 0; }")

        self.manager.tree = QTreeView()
        self.manager.tree.setFrameShape(QFrame.Shape.NoFrame)
        self.manager.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.manager.tree.customContextMenuRequested.connect(self.manager.show_context_menu)
        self.manager.tree.clicked.connect(self.manager.item_clicked)
        self.manager.tree.doubleClicked.connect(self.manager.item_double_clicked)
        self.manager.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.manager.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.manager.tree.setHeaderHidden(True)
        self.manager.tree.setIndentation(15)

        self.manager.model = QStandardItemModel()
        self.manager.model.setHorizontalHeaderLabels(['Object Explorer'])

        self.manager.proxy_model = QSortFilterProxyModel()
        self.manager.proxy_model.setSourceModel(self.manager.model)
        self.manager.proxy_model.setRecursiveFilteringEnabled(True)
        self.manager.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.manager.tree.setModel(self.manager.proxy_model)
        self.manager.tree.setStyleSheet("QTreeView { border: none; margin: 0; padding: 0; background-color: white; }")

        self.manager.vertical_splitter.addWidget(self.manager.tree)

        self.manager.schema_tree = QTreeView()
        self.manager.schema_tree.setFrameShape(QFrame.Shape.NoFrame)
        self.manager.schema_model = QStandardItemModel()
        self.manager.schema_model.setHorizontalHeaderLabels(["Database Schema"])
        self.manager.schema_tree.setModel(self.manager.schema_model)
        self.apply_schema_header_style()
        self.manager.schema_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.manager.schema_tree.customContextMenuRequested.connect(self.manager.show_schema_context_menu)
        self.manager.schema_tree.doubleClicked.connect(self.manager.schema_item_double_clicked)
        self.manager.schema_tree.setIndentation(15)

        self.manager.schema_tree.header().resizeSection(0, 160)

        self.manager.vertical_splitter.addWidget(self.manager.schema_tree)
        self.manager.vertical_splitter.setSizes([240, 360])

        layout.addWidget(object_explorer_header)
        layout.addWidget(self.manager.vertical_splitter)

    def apply_schema_header_style(self):
        header = self.manager.schema_tree.header()
        header.setFixedHeight(36)
        header.setMinimumSectionSize(50)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #9FA6AF;
                color: #ffffff;
                font-weight: bold;
                font-size: 10pt;
                padding: 3px 8px;
                border: none;
                border-bottom: 1px solid #8B929B;
                border-right: 1px solid #B8BEC6;
            }
            QHeaderView::section:last {
                border-right: none;
            }
        """)
