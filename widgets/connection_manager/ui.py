import os

import db
from PySide6.QtWidgets import (
    QVBoxLayout, QWidget, QHBoxLayout, QLabel, QToolButton,
    QSplitter, QTreeView, QFrame, QAbstractItemView, QHeaderView,
    QSizePolicy
)
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QStandardItemModel
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
        self.manager.explorer_search_layout.setSpacing(4)

        self.manager.explorer_search_box = SearchBox("Filter... (Esc to close)")
        self.manager.explorer_search_box.setObjectName("explorer_search_box")
        self.manager.explorer_search_box.setMinimumWidth(0)
        self.manager.explorer_search_box.setClearButtonEnabled(True)
        self.manager.explorer_search_box.hide()

        search_icon_path = "assets/search.svg"
        if not os.path.exists(search_icon_path) and hasattr(db, "resource_path"):
            search_icon_path = db.resource_path("assets/search.svg")
        search_icon = QIcon(search_icon_path if os.path.exists(search_icon_path) else "")
        self.manager.explorer_search_box.textChanged.connect(self.manager.filter_object_explorer)
        self.manager.explorer_search_box.installEventFilter(self.manager)

        self.manager.explorer_search_close_btn = QToolButton()
        self.manager.explorer_search_close_btn.setIcon(qta.icon("mdi.close", color="#6b7280"))
        self.manager.explorer_search_close_btn.setFixedSize(22, 22)
        self.manager.explorer_search_close_btn.setIconSize(QSize(14, 14))
        self.manager.explorer_search_close_btn.setToolTip("Close Filter (Esc)")
        self.manager.explorer_search_close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manager.explorer_search_close_btn.setProperty("class", "sidebar-tool-btn")
        self.manager.explorer_search_close_btn.clicked.connect(self.manager.hide_explorer_search)
        self.manager.explorer_search_close_btn.hide()

        self.manager.explorer_search_btn = QToolButton()
        self.manager.explorer_search_btn.setIcon(search_icon)
        self.manager.explorer_search_btn.setFixedSize(24, 24)
        self.manager.explorer_search_btn.setIconSize(QSize(16, 16))
        self.manager.explorer_search_btn.setToolTip("Search Connections")
        self.manager.explorer_search_btn.setProperty("class", "sidebar-tool-btn")
        self.manager.explorer_search_btn.clicked.connect(self.manager.toggle_explorer_search)

        self.manager.explorer_search_spacer = QWidget()
        self.manager.explorer_search_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self.manager.explorer_search_layout.addWidget(self.manager.explorer_search_spacer)
        self.manager.explorer_search_layout.addWidget(self.manager.explorer_search_box, 1)
        self.manager.explorer_search_layout.addWidget(self.manager.explorer_search_close_btn)
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

        object_explorer_header_layout.addWidget(self.manager.explorer_search_container, 1)
        object_explorer_header_layout.addWidget(self.add_new_type_btn)

        # Collapse / expand sidebar button — stays visible even when collapsed
        self.manager.collapse_panel_btn = QToolButton()
        self.manager.collapse_panel_btn.setFixedSize(24, 24)
        self.manager.collapse_panel_btn.setIconSize(QSize(16, 16))
        self.manager.collapse_panel_btn.setToolTip("Collapse Sidebar")
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
        self.manager.tree.setIndentation(16)
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
        self.manager.schema_tree.setViewportMargins(0, 0, 0, 0)
        self.manager.schema_model = QStandardItemModel()
        self.manager.schema_model.setHorizontalHeaderLabels(["Database Schema"])
        self.manager.schema_tree.setModel(self.manager.schema_model)
        self.apply_schema_header_style()
        self.manager.schema_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.manager.schema_tree.setDragEnabled(True)
        self.manager.schema_tree.customContextMenuRequested.connect(self.manager.show_schema_context_menu)
        self.manager.schema_tree.doubleClicked.connect(self.manager.schema_item_double_clicked)
        self.manager.schema_tree.setIndentation(16)

        self.manager.schema_tree.header().resizeSection(0, 140)

        # Header corner widget so vertical scrollbar starts below the header
        self.manager.schema_header_corner = QWidget()
        self.manager.schema_header_corner.setObjectName("schemaHeaderCorner")
        self.manager.schema_header_corner.setFixedHeight(36)
        self.manager.schema_tree.addScrollBarWidget(
            self.manager.schema_header_corner, Qt.AlignmentFlag.AlignTop
        )

        # ── Bottom Search & Footer Container ──
        self.manager.schema_bottom_container = QWidget()
        self.manager.schema_bottom_container.setObjectName("schemaBottomContainer")
        self.manager.schema_bottom_container.setStyleSheet(
            "background-color: #f3f4f6; border-top: 1px solid #d1d5db;"
        )
        bottom_main_layout = QVBoxLayout(self.manager.schema_bottom_container)
        bottom_main_layout.setContentsMargins(0, 0, 0, 0)
        bottom_main_layout.setSpacing(0)

        # 1. Collapsed bottom bar (status label on left, 🔍 search button on right)
        self.manager.schema_bottom_bar = QWidget()
        self.manager.schema_bottom_bar.setFixedHeight(28)
        bar_layout = QHBoxLayout(self.manager.schema_bottom_bar)
        bar_layout.setContentsMargins(8, 2, 6, 2)
        bar_layout.setSpacing(6)

        self.manager.schema_status_label = QLabel("")
        self.manager.schema_status_label.setStyleSheet("color: #6b7280; font-size: 11px;")
        self.manager._default_schema_status = ""

        self.manager.schema_search_btn = QToolButton(self.manager.schema_tree.header())
        self.manager.schema_search_btn.setObjectName("schemaSearchBtn")
        self.manager.schema_search_btn.setIcon(search_icon)
        self.manager.schema_search_btn.setFixedSize(24, 24)
        self.manager.schema_search_btn.setIconSize(QSize(16, 16))
        self.manager.schema_search_btn.setToolTip("Filter tables (Ctrl+F)")
        self.manager.schema_search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manager.schema_search_btn.setProperty("class", "sidebar-tool-btn")
        self.manager.schema_search_btn.clicked.connect(self.manager.show_schema_search)
        self.manager.schema_tree.header().installEventFilter(self.manager)

        bar_layout.addWidget(self.manager.schema_status_label)
        bar_layout.addStretch()
        bottom_main_layout.addWidget(self.manager.schema_bottom_bar)

        # 2. Expanded search box widget (replaces Name/Type header when active)
        self.manager.schema_search_container = QWidget()
        self.manager.schema_search_container.setObjectName("schemaSearchContainer")
        self.manager.schema_search_container.setFixedHeight(36)
        self.manager.schema_search_container.setStyleSheet(
            "#schemaSearchContainer { background-color: #E4E8ED; border-bottom: 1px solid #D3D8DF; }"
        )
        search_layout = QHBoxLayout(self.manager.schema_search_container)
        search_layout.setContentsMargins(6, 4, 6, 4)
        search_layout.setSpacing(4)

        self.manager.schema_search_box = SearchBox("Filter tables... (Esc to close)")
        self.manager.schema_search_box.setObjectName("schema_search_box")
        self.manager.schema_search_box.setClearButtonEnabled(True)
        self.manager.schema_search_box.textChanged.connect(self.manager.filter_schema_tree)
        self.manager.schema_search_box.installEventFilter(self.manager)

        self.manager.schema_search_close_btn = QToolButton()
        self.manager.schema_search_close_btn.setIcon(qta.icon("mdi.close", color="#6b7280"))
        self.manager.schema_search_close_btn.setFixedSize(22, 22)
        self.manager.schema_search_close_btn.setIconSize(QSize(14, 14))
        self.manager.schema_search_close_btn.setToolTip("Close Filter (Esc)")
        self.manager.schema_search_close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manager.schema_search_close_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
                border-radius: 3px;
            }
            QToolButton:hover {
                background: rgba(128, 128, 128, 0.25);
            }
        """)
        self.manager.schema_search_close_btn.clicked.connect(self.manager.hide_schema_search)

        search_layout.addWidget(self.manager.schema_search_box)
        search_layout.addWidget(self.manager.schema_search_close_btn)
        self.manager.schema_search_container.hide()

        # Keyboard Shortcut: Ctrl+F on schema pane toggles search
        self.manager.schema_search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self.manager.schema_tree)
        self.manager.schema_search_shortcut.activated.connect(self.manager.toggle_schema_search)

        self.manager.schema_tree.installEventFilter(self.manager)

        # Schema Pane: Search bar (when active) at top, tree below
        self.manager.schema_bottom_container.hide()
        self.manager.schema_pane = QWidget()
        self.manager.schema_pane.setObjectName("schemaPane")
        schema_pane_layout = QVBoxLayout(self.manager.schema_pane)
        schema_pane_layout.setContentsMargins(0, 0, 0, 0)
        schema_pane_layout.setSpacing(0)
        schema_pane_layout.addWidget(self.manager.schema_search_container)
        schema_pane_layout.addWidget(self.manager.schema_tree)

        self.manager.vertical_splitter.addWidget(self.manager.schema_pane)
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
        self.manager.collapsed_new_ws_btn.setIcon(qta.icon('mdi.file-document-edit', color="#6b7280"))
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
