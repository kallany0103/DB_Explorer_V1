import os

from PySide6.QtWidgets import (
    QVBoxLayout, QWidget, QHBoxLayout, QLabel, QToolButton,
    QSplitter, QTreeView, QFrame, QAbstractItemView, QHeaderView
)
from PySide6.QtGui import QIcon, QStandardItemModel
from PySide6.QtCore import Qt, QSize, QSortFilterProxyModel
from ui.components import SearchBox
import qtawesome as qta


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

        object_explorer_header_layout = QHBoxLayout(object_explorer_header)
        object_explorer_header_layout.setContentsMargins(8, 2, 8, 6)
        object_explorer_header_layout.setSpacing(10)
        # Store ref so toggle_left_panel() can adjust margins when collapsing
        self.manager.explorer_header_layout = object_explorer_header_layout

        object_explorer_label = QLabel("Object Explorer")
        object_explorer_label.setObjectName("objectExplorerLabel")
        object_explorer_label.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        # Store ref so toggle_left_panel() can hide/show it
        self.manager.explorer_label = object_explorer_label

        object_explorer_header_layout.addWidget(object_explorer_label)

        self.manager.explorer_search_container = QWidget()
        self.manager.explorer_search_layout = QHBoxLayout(self.manager.explorer_search_container)
        self.manager.explorer_search_layout.setContentsMargins(0, 0, 0, 0)
        self.manager.explorer_search_layout.setSpacing(0)

        self.manager.explorer_search_box = SearchBox("Filter...")
        self.manager.explorer_search_box.setObjectName("explorer_search_box")
        self.manager.explorer_search_box.setMinimumWidth(120)
        self.manager.explorer_search_box.hide()

        search_icon_path = "assets/search.svg"
        self.manager.explorer_search_box.textChanged.connect(self.manager.filter_object_explorer)
        self.manager.explorer_search_box.installEventFilter(self.manager)


        self.manager.explorer_search_btn = QToolButton()
        self.manager.explorer_search_btn.setIcon(QIcon(search_icon_path if os.path.exists(search_icon_path) else ""))
        self.manager.explorer_search_btn.setFixedSize(24, 24)
        self.manager.explorer_search_btn.setIconSize(QSize(16, 16))
        self.manager.explorer_search_btn.setToolTip("Search Connections")
        self.manager.explorer_search_btn.setProperty("class", "sidebar-tool-btn")
        self.manager.explorer_search_btn.clicked.connect(self.manager.toggle_explorer_search)

        self.manager.explorer_search_layout.addWidget(self.manager.explorer_search_box)
        self.manager.explorer_search_layout.addWidget(self.manager.explorer_search_btn)

                         # New Connection Type
        self.add_new_type_btn = QToolButton()
        self.add_new_type_btn.setFixedSize(24, 24)
        self.add_new_type_btn.setIconSize(QSize(16, 16))
        self.add_new_type_btn.setToolTip("Add New Connection")
        self.add_new_type_btn.setIcon(qta.icon("mdi.database-plus", color="#6b7280"))
        self.add_new_type_btn.setProperty("class", "sidebar-tool-btn")
        self.add_new_type_btn.clicked.connect(self.manager.add_connection_flow)
        # Store ref so toggle_left_panel() can hide/show it
        self.manager.explorer_add_btn = self.add_new_type_btn

        object_explorer_header_layout.addStretch()
        object_explorer_header_layout.addWidget(self.manager.explorer_search_container)
        object_explorer_header_layout.addWidget(self.add_new_type_btn)

        # Collapse / expand sidebar button — stays visible even when collapsed
        self.manager.collapse_panel_btn = QToolButton()
        self.manager.collapse_panel_btn.setFixedSize(24, 24)
        self.manager.collapse_panel_btn.setIconSize(QSize(16, 16))
        self.manager.collapse_panel_btn.setToolTip("Hide Sidebar")
        self.manager.collapse_panel_btn.setProperty("class", "sidebar-tool-btn")
        self.manager.collapse_panel_btn.setIcon(qta.icon('mdi.chevron-double-left', color='#6b7280'))
        self.manager.collapse_panel_btn.clicked.connect(
            lambda: self.manager.main_window.toggle_left_panel()
        )
        object_explorer_header_layout.addWidget(self.manager.collapse_panel_btn)

        self.manager.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self.manager.vertical_splitter.setHandleWidth(0)
        self.manager.vertical_splitter.setStyleSheet("QSplitter { border: none; margin: 0; padding: 0; }")

        self.manager.tree = QTreeView()
        self.manager.tree.setObjectName("connectionTree")
        self.manager.tree.setFrameShape(QFrame.Shape.NoFrame)
        self.manager.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.manager.tree.customContextMenuRequested.connect(self.manager.show_context_menu)
        self.manager.tree.clicked.connect(self.manager.item_clicked)
        self.manager.tree.doubleClicked.connect(self.manager.item_double_clicked)
        self.manager.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.manager.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.manager.tree.setHeaderHidden(True)
        self.manager.tree.setIndentation(15)
        self.manager.tree.setUniformRowHeights(True)

        self.manager.model = QStandardItemModel()
        self.manager.model.setHorizontalHeaderLabels(['Object Explorer'])

        self.manager.proxy_model = QSortFilterProxyModel()
        self.manager.proxy_model.setSourceModel(self.manager.model)
        self.manager.proxy_model.setRecursiveFilteringEnabled(True)
        self.manager.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.manager.tree.setModel(self.manager.proxy_model)


        self.manager.vertical_splitter.addWidget(self.manager.tree)

        self.manager.schema_tree = QTreeView()
        self.manager.schema_tree.setFrameShape(QFrame.Shape.NoFrame)
        self.manager.schema_model = QStandardItemModel()
        self.manager.schema_model.setHorizontalHeaderLabels(["Database Schema"])
        self.manager.schema_tree.setModel(self.manager.schema_model)
        self.apply_schema_header_style()
        self.manager.schema_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.manager.schema_tree.setDragEnabled(True)
        self.manager.schema_tree.customContextMenuRequested.connect(self.manager.show_schema_context_menu)
        self.manager.schema_tree.doubleClicked.connect(self.manager.schema_item_double_clicked)
        self.manager.schema_tree.setIndentation(15)

        self.manager.schema_tree.header().resizeSection(0, 160)

        self.manager.vertical_splitter.addWidget(self.manager.schema_tree)
        self.manager.vertical_splitter.setSizes([240, 360])

        layout.addWidget(object_explorer_header)

        # ── COLLAPSED TOOLS WIDGET ──
        self.manager.collapsed_tools_widget = QWidget()
        collapsed_layout = QVBoxLayout(self.manager.collapsed_tools_widget)
        collapsed_layout.setContentsMargins(2, 10, 2, 0)
        collapsed_layout.setSpacing(10)
        collapsed_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # New Connection Button
        self.manager.collapsed_add_conn_btn = QToolButton()
        self.manager.collapsed_add_conn_btn.setFixedSize(24, 24)
        self.manager.collapsed_add_conn_btn.setIconSize(QSize(16, 16))
        self.manager.collapsed_add_conn_btn.setToolTip("Add New Connection")
        self.manager.collapsed_add_conn_btn.setIcon(qta.icon("mdi.database-plus", color="#6b7280"))
        self.manager.collapsed_add_conn_btn.setProperty("class", "sidebar-tool-btn")
        self.manager.collapsed_add_conn_btn.clicked.connect(self.manager.add_connection_flow)

        # New Worksheet Button
        self.manager.collapsed_new_ws_btn = QToolButton()
        self.manager.collapsed_new_ws_btn.setFixedSize(24, 24)
        self.manager.collapsed_new_ws_btn.setIconSize(QSize(16, 16))
        self.manager.collapsed_new_ws_btn.setToolTip("New Worksheet")
        self.manager.collapsed_new_ws_btn.setIcon(qta.icon('mdi.database-edit', color="#6b7280"))
        self.manager.collapsed_new_ws_btn.setProperty("class", "sidebar-tool-btn")
        self.manager.collapsed_new_ws_btn.clicked.connect(lambda: self.manager.main_window.add_tab())

        # New ERD Button
        self.manager.collapsed_new_erd_btn = QToolButton()
        self.manager.collapsed_new_erd_btn.setFixedSize(24, 24)
        self.manager.collapsed_new_erd_btn.setIconSize(QSize(16, 16))
        self.manager.collapsed_new_erd_btn.setToolTip("New ERD")
        self.manager.collapsed_new_erd_btn.setIcon(qta.icon('fa6s.sitemap', color="#6b7280"))
        self.manager.collapsed_new_erd_btn.setProperty("class", "sidebar-tool-btn")
        self.manager.collapsed_new_erd_btn.clicked.connect(lambda: self.manager.main_window.add_erd_tab())

        collapsed_layout.addWidget(self.manager.collapsed_add_conn_btn)
        collapsed_layout.addWidget(self.manager.collapsed_new_ws_btn)
        collapsed_layout.addWidget(self.manager.collapsed_new_erd_btn)
        
        self.manager.collapsed_tools_widget.hide()
        layout.addWidget(self.manager.collapsed_tools_widget)
        # ────────────────────────────

        layout.addWidget(self.manager.vertical_splitter)

        self.manager.empty_space = QWidget()
        self.manager.empty_space.hide()
        layout.addWidget(self.manager.empty_space, 1)

    def apply_schema_header_style(self):
        header = self.manager.schema_tree.header()
        header.setObjectName("schemaTreeHeader")
        header.setFixedHeight(36)
        header.setMinimumSectionSize(50)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
