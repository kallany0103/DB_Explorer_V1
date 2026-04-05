import json
import heapq
from collections import deque
from datetime import datetime
import qtawesome as qta
# from PyQt6.QtWidgets import (
#     QWidget, QVBoxLayout, QHBoxLayout,
#     QToolBar, QFileDialog, QMessageBox, QDialog,
#     QTextEdit, QDialogButtonBox, QToolButton, QLineEdit, QMenu, QSplitter
# )
# from PyQt6.QtGui import QAction, QTransform, QPixmap, QPainter, QFont, QColor, QUndoStack, QPdfWriter, QPageSize
# from PyQt6.QtCore import Qt, QSize, QEvent, QRectF, QTimer, QPointF
#from PyQt6.QtSvg import QSvgGenerator


from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QFileDialog, QMessageBox, QDialog,
    QTextEdit, QDialogButtonBox, QToolButton, QLineEdit, QMenu, QSplitter
)
from PySide6.QtGui import QAction, QTransform, QPixmap, QPainter, QFont, QColor, QUndoStack, QPdfWriter, QPageSize
from PySide6.QtCore import Qt, QSize, QEvent, QRectF, QTimer, QPointF
from PySide6.QtSvg import QSvgGenerator

from widgets.erd.items.table_item import ERDTableItem
from widgets.erd.items.connection_item import ERDConnectionItem
from widgets.erd.scene import ERDScene
from widgets.erd.view import ERDView
from widgets.erd.property_panel import PropertyPanel

class SQLPreviewDialog(QDialog):
    def __init__(self, sql_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SQL Script")
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowSystemMenuHint)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(sql_text)
        self.text_edit.setFont(QFont("Consolas", 10))
        layout.addWidget(self.text_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close)
        buttons.accepted.connect(self.save_sql)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save_sql(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save SQL Script", "schema.sql", "SQL Files (*.sql)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.text_edit.toPlainText())
                QMessageBox.information(self, "Success", "SQL script saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save script: {str(e)}")



def generate_sql_script(schema_data):
    """
    Generates an SQL script for the given schema data.
    Returns the SQL script as a string.
    """
    def quote_ident(ident: str) -> str:
        """Quote SQL identifiers safely, handling dotted names."""
        parts = ident.split('.')
        quoted = []
        for p in parts:
            p2 = p.replace('"', '""')
            quoted.append(f'"{p2}"')
        return '.'.join(quoted)

    def quote_default(dval):
        """Heuristic quoting for default values: leave function/cast forms, quote plain strings."""
        if dval is None:
            return 'NULL'
        if not isinstance(dval, str):
            return str(dval)
        s = dval.strip()
        if s.startswith("'") and s.endswith("'"):
            return s
        if '(' in s or '::' in s:
            return s
        return "'" + s.replace("'", "''") + "'"

    # --- ALGORITHM: Topological Sort (Kahn's Algorithm) ---
    # Ensures tables are created in the correct order to satisfy foreign key constraints.
    # Uses a Min-Heap (heapq) to maintain a deterministic, alphabetically-sorted order 
    # for tables at the same dependency level.
    adj = {name: [] for name in schema_data.keys()}
    in_degree = {name: 0 for name in schema_data.keys()}
    for name, info in schema_data.items():
        for fk in info.get('foreign_keys', []):
            target = fk['table']
            if target in in_degree:
                adj.setdefault(target, []).append(name)
                in_degree[name] += 1

    heap = [n for n in schema_data.keys() if in_degree[n] == 0]
    heapq.heapify(heap)
    ordered_tables = []
    while heap:
        u = heapq.heappop(heap)
        ordered_tables.append(u)
        for v in adj.get(u, []):
            in_degree[v] -= 1
            if in_degree[v] == 0:
                heapq.heappush(heap, v)

    # Append remaining tables (detects/handles dependency cycles) in deterministic order
    for name in sorted(schema_data.keys()):
        if name not in ordered_tables:
            ordered_tables.append(name)

    # Generate SQL script
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sql_lines = [
        "-- ===========================================================================",
        "-- ENTERPRISE DATA MODEL EXPORT",
        f"-- Generated on: {gen_time}",
        "-- Engine: PostgreSQL / Standard SQL Compatibility",
        "-- Description: ",
        "-- ===========================================================================\n",
        "BEGIN TRANSACTION;\n"
    ]

    for full_table_name in ordered_tables:
        info = schema_data[full_table_name]
        schema = info.get('schema', 'public')
        table_name = info.get('table', full_table_name.split('.')[-1])

        sql_lines.append(f"CREATE TABLE IF NOT EXISTS {quote_ident(schema)}.{quote_ident(table_name)}")
        sql_lines.append("(")

        col_lines = []
        pk_cols = []

        for col in info['columns']:
            col_name = col['name']
            data_type = col['type'].lower()

            # Handle primary keys and serial types
            is_pk = col.get('pk')
            if is_pk:
                pk_cols.append(col_name)       
                if "int" in data_type:  #need to resolve this better, but for now we assume any int PK is serial
                    data_type = "serial"

            # Normalize varchar/text types
            if "varchar" in data_type or "varying" in data_type or "text" in data_type:
                if "(" not in data_type and "text" not in data_type:
                    data_type = "character varying(255)"
                data_type += ' COLLATE pg_catalog."default"'

            col_def = f"    {quote_ident(col_name)} {data_type}"
            if col.get('nullable') is False or is_pk:
                col_def += " NOT NULL"
            if 'default' in col and col.get('default') is not None:
                col_def += f" DEFAULT {quote_default(col['default'])}"

            col_lines.append(col_def)

        if pk_cols:
            pk_name = f"{table_name}_pkey"
            pk_cols_q = ', '.join(quote_ident(c) for c in pk_cols)
            col_lines.append(f"    CONSTRAINT {quote_ident(pk_name)} PRIMARY KEY ({pk_cols_q})")

        for fk in info.get('foreign_keys', []):
            fk_name = fk.get('name', f"fk_{table_name}_{fk['from']}")
            target_schema = schema_data.get(fk['table'], {}).get('schema', 'public')
            target_table = fk['table'].split('.')[-1]
            col_lines.append(
                f"    CONSTRAINT {quote_ident(fk_name)} FOREIGN KEY ({quote_ident(fk['from'])}) "
                f"REFERENCES {quote_ident(target_schema)}.{quote_ident(target_table)}({quote_ident(fk['to'])})"
            )

        sql_lines.append(",\n".join(col_lines))
        sql_lines.append(" );\n")

    sql_lines.append("COMMIT;")
    return "\n".join(sql_lines)

class ERDWidget(QWidget):
    def __init__(self, schema_data, parent=None):
        super().__init__(parent)
        self.schema_data = schema_data
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Toolbar Container to hold the styled toolbar
        toolbar_container = QWidget()
        toolbar_container.setObjectName("erdToolbarContainer")
        toolbar_container.setStyleSheet("""
            #erdToolbarContainer {
                background-color: #f0f0f0;
                border-bottom: 1px solid #c6c6c6;
                padding: 0px 6px;
            }
            QToolBar {
                background: transparent;
                border: none;
                spacing: 6px;
            }
            QToolButton {
                padding: 2px 8px;
                border: 1px solid #b9b9b9;
                background-color: #ffffff;
                border-radius: 4px;
                font-size: 9pt;
                color: #333333;
            }
            QToolButton:hover {
                background-color: #e8e8e8;
                border: 1px solid #9c9c9c;
            }
            QToolButton:pressed {
                background-color: #dcdcdc;
            }
        """)
        
        container_layout = QHBoxLayout(toolbar_container)
        container_layout.setContentsMargins(6, 3, 6, 3)
        
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(16, 16))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        
        # Group 1: File Operations
        open_action = QAction(qta.icon('fa5s.folder-open', color='#555555'), "Open ERD (.erd)", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.load_erd_file)
        self.toolbar.addAction(open_action)
        
        save_action = QAction(qta.icon('fa5s.save', color='#555555'), "Save ERD (.erd)", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_erd)
        self.toolbar.addAction(save_action)

        export_png = QAction(qta.icon('fa5s.image', color='#555555'), "Export to PNG", self)
        export_png.triggered.connect(lambda: self.save_as_image("png"))
        self.toolbar.addAction(export_png)

        export_svg = QAction(qta.icon('fa5s.vector-square', color='#555555'), "Export to SVG", self)
        export_svg.triggered.connect(lambda: self.save_as_image("svg"))
        self.toolbar.addAction(export_svg)

        export_pdf = QAction(qta.icon('fa5s.file-pdf', color='#555555'), "Export to PDF", self)
        export_pdf.triggered.connect(lambda: self.save_as_image("pdf"))
        self.toolbar.addAction(export_pdf)
        
        self.toolbar.addSeparator()
        
        # Group 2: View Controls
        zoom_in_action = QAction(qta.icon('fa5s.search-plus', color='#555555'), "Zoom In", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(lambda: self.view.scale(1.2, 1.2))
        self.toolbar.addAction(zoom_in_action)
        
        zoom_out_action = QAction(qta.icon('fa5s.search-minus', color='#555555'), "Zoom Out", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(lambda: self.view.scale(0.8, 0.8))
        self.toolbar.addAction(zoom_out_action)
        
        reset_zoom_action = QAction(qta.icon('fa5s.expand-arrows-alt', color='#555555'), "Zoom to Fit", self)
        reset_zoom_action.setShortcut("Ctrl+0")
        reset_zoom_action.triggered.connect(lambda: self.view.setTransform(QTransform()))
        self.toolbar.addAction(reset_zoom_action)
        
        self.toolbar.addSeparator()
        
        self.undo_stack = QUndoStack(self)
        
        # Group 3: Auto Align & History
        align_action = QAction(qta.icon('fa5s.th', color='#555555'), "Auto Align", self)
        align_action.setShortcut("Alt+Ctrl+L")
        align_action.triggered.connect(self.auto_layout)
        self.toolbar.addAction(align_action)
        
        # Undo/Redo
        self.undo_action = self.undo_stack.createUndoAction(self, "Undo")
        self.undo_action.setIcon(qta.icon('fa5s.undo', color='#555555'))
        self.undo_action.setShortcut("Ctrl+Z")
        self.toolbar.addAction(self.undo_action)
        
        self.redo_action = self.undo_stack.createRedoAction(self, "Redo")
        self.redo_action.setIcon(qta.icon('fa5s.redo', color='#555555'))
        self.redo_action.setShortcut("Ctrl+Y")
        self.toolbar.addAction(self.redo_action)

        self.toolbar.addSeparator()

        # Group 4: Panel & Visibility
        self.show_details_action = QAction(qta.icon('fa5s.eye', color='#555555'), "Show Details", self)
        self.show_details_action.setShortcut("Alt+Ctrl+T")
        self.show_details_action.setCheckable(True)
        self.show_details_action.setChecked(True)
        self.show_details_action.triggered.connect(self.toggle_details)
        self.toolbar.addAction(self.show_details_action)

        self.show_types_action = QAction(qta.icon('fa5s.font', color='#555555'), "Show Data Types", self)
        self.show_types_action.setShortcut("Alt+Ctrl+D")
        self.show_types_action.setCheckable(True)
        self.show_types_action.setChecked(True)
        self.show_types_action.triggered.connect(self.toggle_types)
        self.toolbar.addAction(self.show_types_action)
        
        self.show_panel_action = QAction(qta.icon('fa5s.columns', color='#555555'), "Toggle Panel", self)
        self.show_panel_action.setCheckable(True)
        self.show_panel_action.setChecked(True)
        self.show_panel_action.triggered.connect(self.toggle_panel)
        self.toolbar.addAction(self.show_panel_action)
        
        self.toolbar.addSeparator()
        
        # Group 5: Advanced Tools
        self.sql_btn = QToolButton()
        self.sql_btn.setIcon(qta.icon('fa5s.database', color='#555555'))
        self.sql_btn.setIconSize(QSize(16, 16))
        self.sql_btn.setFixedHeight(30)
        self.sql_btn.setMinimumWidth(26)
        self.sql_btn.setToolTip("Generate SQL Script (Alt+Ctrl+S)")
        
        # Connection
        self.sql_btn.clicked.connect(self.generate_forward_sql)
        self.toolbar.addWidget(self.sql_btn)
        
        # Add a shortcut too
        self.sql_shortcut = QAction(self)
        self.sql_shortcut.setShortcut("Alt+Ctrl+S")
        self.sql_shortcut.triggered.connect(self.generate_forward_sql)
        self.addAction(self.sql_shortcut)
        
        container_layout.addWidget(self.toolbar)
        # Search Bar (Toggle UI)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.setFixedHeight(28)
        self.search_input.setFixedWidth(180)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding-left: 5px;
                padding-right: 5px;
            }
            QLineEdit:focus {
                border: 1px solid #1A73E8;
            }
        """)
        self.search_input.hide() # Initially hidden
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.search_input.returnPressed.connect(self.on_search_return_pressed)
        # Install event filter to auto-hide on focus out
        self.search_input.installEventFilter(self)

        self.search_btn = QToolButton()
        self.search_btn.setIcon(qta.icon('fa5s.search', color='#555555'))
        self.search_btn.setIconSize(QSize(16, 16))
        self.search_btn.setFixedHeight(30)
        self.search_btn.setMinimumWidth(26)
        self.search_btn.setToolTip("Search (Ctrl+F)")
        self.search_btn.clicked.connect(self.toggle_search)

        # Add to toolbar layout BEFORE the stretch
        container_layout.addWidget(self.search_input)
        container_layout.addWidget(self.search_btn)
        
        container_layout.addStretch()

        search_action = QAction(self)
        search_action.setShortcut("Ctrl+F")
        search_action.triggered.connect(self.toggle_search)
        self.addAction(search_action)

        layout.addWidget(toolbar_container)
        
        # Scene and View
        self.scene = ERDScene(self)
        self.scene.undo_stack = self.undo_stack
        self.view = ERDView(self.scene, self)
        
        # Main Area (No splitters)
        self.view_container = QWidget()
        self.view_layout = QVBoxLayout(self.view_container)
        self.view_layout.setContentsMargins(0, 0, 0, 0)
        self.view_layout.addWidget(self.view)
        
        # Overlay Floating Property Panel
        self.property_panel = PropertyPanel(self.view, self.view_container)
        self.property_panel.hide() # Hidden by default
        
        # Make the view take all extra space
        
        layout.addWidget(self.view_container)
        
        # Update layout initially and on resize
        self.view_container.installEventFilter(self)
        
        self.load_schema()
        self.auto_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)

    def _center_view_deferred(self):
        if self.scene.items():
            rect = self.scene.itemsBoundingRect()
            # Reset zoom to 100% (scale 1.0)
            self.view.setTransform(QTransform())
            # Center on the top row of items
            top_center = QPointF(rect.center().x(), rect.top() + rect.height() * 0.25)
            self.view.centerOn(top_center)

    def toggle_search(self):
        if self.search_input.isVisible():
            self.search_input.hide()
            self.search_btn.show()
            self.search_input.clear() # Optional: Clear search on close
        else:
            self.search_btn.hide()
            self.search_input.show()
            self.search_input.setFocus()

    def eventFilter(self, obj, event):
        if obj == getattr(self, 'search_input', None) and event.type() == event.Type.FocusOut:
            if not self.search_input.text():
                self.toggle_search()
        elif hasattr(self, 'view_container') and obj == self.view_container and event.type() == event.Type.Resize:
            self._update_panel_geometry()
        return super().eventFilter(obj, event)

    def _update_panel_geometry(self):
        if hasattr(self, 'property_panel') and self.property_panel.isVisible():
            # Stick to Top Right with 20px padding
            container_rect = self.view_container.rect()
            panel_width = self.property_panel.width()
            panel_height = self.property_panel.sizeHint().height()
            
            # Clamp height to not exceed container (with padding)
            max_h = container_rect.height() - 40
            panel_height = min(panel_height, max_h)
            
            x = container_rect.width() - panel_width - 20
            y = 20
            self.property_panel.setGeometry(int(x), int(y), int(panel_width), int(panel_height))

    def generate_forward_sql(self):
        """
        Generates the SQL script and displays it in a preview dialog.
        """
        sql_script = generate_sql_script(self.schema_data)
        dialog = SQLPreviewDialog(sql_script, self)
        dialog.exec()

    def load_schema(self):
        # Color palette for Subject Areas (Subject Area Highlighting)
        GROUP_COLORS = [
            QColor("#E8F0FE"), # Blue
            QColor("#FCE8E6"), # Red
            QColor("#E6F4EA"), # Green
            QColor("#FEF7E0"), # Yellow
            QColor("#F3E5F5"), # Purple
            QColor("#E0F7FA"), # Cyan
            QColor("#FFF0E0"), # Orange
            QColor("#F0F0F0"), # Gray
        ]

        # 1. Create table items
        for full_name, table_info in self.schema_data.items():
            table_name = table_info.get('table', full_name)
            schema_name = table_info.get('schema')
            
            columns = table_info['columns']
            fk_cols = {fk['from'] for fk in table_info.get('foreign_keys', [])}
            for col in columns:
                if col['name'] in fk_cols:
                    col['fk'] = True
            
            table_item = ERDTableItem(table_name, columns, schema_name=schema_name)
            self.scene.addItem(table_item)
            self.scene.tables[full_name] = table_item

        # 2. --- ALGORITHM: Connected Components (Graph Theory) ---
        # Detects clusters of tables that are linked together (Subject Areas).
        # Uses an adjacency list and BFS/DFS traversal to identify independent subgraphs.
        adj = {name: [] for name in self.schema_data.keys()}
        for full_name, table_info in self.schema_data.items():
            for fk in table_info.get('foreign_keys', []):
                target = fk['table']
                if target in adj:
                    adj[full_name].append(target)
                    adj[target].append(full_name)
        
        visited = set()
        group_idx = 0
        for name in self.schema_data.keys():
            if name not in visited:
                # New Group identified via Stack-based DFS
                component = []
                stack = [name]
                while stack:
                    curr = stack.pop()
                    if curr not in visited:
                        visited.add(curr)
                        component.append(curr)
                        stack.extend(adj[curr])
                
                # Assign a distinct color to this Subject Area
                color = GROUP_COLORS[group_idx % len(GROUP_COLORS)]
                for comp_name in component:
                    if comp_name in self.scene.tables:
                        self.scene.tables[comp_name].group_color = color
                group_idx += 1
            
        # 3. Create connection items
        for full_name, table_info in self.schema_data.items():
            source_item = self.scene.tables.get(full_name)
            if not source_item: continue
            
            # Get PK info for source table to detect Identifying relationships
            pk_cols = {col['name'] for col in table_info['columns'] if col.get('pk')}
            
            for fk in table_info.get('foreign_keys', []):
                target_full_name = fk['table']
                target_item = self.scene.tables.get(target_full_name)
                if target_item:
                    # Logic 1: Identifying? If the FK column is part of the PK
                    is_identifying = fk['from'] in pk_cols
                    
                    # Logic 2: Cardinality? Check if the FK column is also marked unique
                    # (Note: In simple schema retrieval, we'll assume uniqueness if it's a 1:1 join)
                    # For now, if the FK itself is the PK, we treat it as potentially 1:1
                    is_unique = (fk['from'] in pk_cols and len(pk_cols) == 1)
                    
                    conn_item = ERDConnectionItem(
                        source_item, target_item, 
                        fk['from'], fk['to'],
                        is_identifying=is_identifying,
                        is_unique=is_unique
                    )
                    self.scene.addItem(conn_item)
        
        self.scene.update_scene_rect()

    def auto_layout(self):
        """
        Main layout orchestrator. Uses a Sugiyama-style hierarchical approach combined 
        with graph component detection to organize tables into a readable ERD.
        """
        if not self.scene.tables:
            return

        # 1. --- ALGORITHM: Connected Component Detection ---
        # Purpose: Identifies disjoint subgraphs (islands of linked tables).
        # This allows the layout engine to process each subject area independently
        # without unrelated tables causing overlap or visual clutter.
        adj_bi = {name: [] for name in self.schema_data.keys()}
        for full_name, table_info in self.schema_data.items():
            for fk in table_info.get('foreign_keys', []):
                target = fk['table']
                if target in self.schema_data:
                    adj_bi[full_name].append(target)
                    adj_bi[target].append(full_name)

        visited = set()
        components = []
        for name in self.schema_data.keys():
            if name not in visited:
                comp = []
                stack = [name]
                while stack:
                    u = stack.pop()
                    if u not in visited:
                        visited.add(u)
                        comp.append(u)
                        for v in adj_bi[u]:
                            if v not in visited:
                                stack.append(v)
                if comp:
                    components.append(comp)

        # Process larger clusters first for predictable vertical stacking
        components.sort(key=len, reverse=True)

        item_map = self.scene.tables
        current_y_offset = 100

        # 2. Layout each component independently using a Hierarchical Flow
        for comp_nodes in components:
            sub_adj = {n: [] for n in comp_nodes}
            sub_in_degree = {n: 0 for n in comp_nodes}
            sub_total_degree = {n: 0 for n in comp_nodes}

            for u in comp_nodes:
                info = self.schema_data[u]
                for fk in info.get('foreign_keys', []):
                    target = fk['table']
                    if target in sub_adj and target != u:
                        sub_adj[target].append(u)
                        sub_in_degree[u] += 1
                        sub_total_degree[u] += 1
                        sub_total_degree[target] += 1

            # --- STEP 2a: RANKING (Sugiyama Layering) ---
            # Assigns tables to vertical columns (ranks) based on dependency depth.
            # Root tables (no FKs) appear on the far left.
            ranks = {n: 0 for n in comp_nodes}
            queue = deque(n for n in comp_nodes if sub_in_degree[n] == 0)

            while queue:
                u = queue.popleft()
                for v in sub_adj[u]:
                    sub_in_degree[v] -= 1
                    ranks[v] = max(ranks[v], ranks[u] + 1)
                    if sub_in_degree[v] == 0:
                        queue.append(v)

            layers = {}
            for n in comp_nodes:
                r = ranks[n]
                if r not in layers: 
                    layers[r] = []
                layers[r].append(n)

            sorted_ranks = sorted(layers.keys())

            # --- STEP 2b: CROSSING REDUCTION (Centrality Sorting) ---
            # Sorts tables within each rank to minimize line intersections.
            # Uses a "Barycenter-like" heuristic by placing high-degree nodes
            # in the center of the vertical stack.
            for r in sorted_ranks:
                nodes = layers[r]
                nodes.sort(key=lambda n: sub_total_degree[n], reverse=True)
                central = deque()
                left = True
                for node in nodes:
                    if left:
                        central.appendleft(node)
                    else:
                        central.append(node)
                    left = not left
                layers[r] = list(central)

            # Position this component with Left-to-Right flow
            padding_x = 180  # More horizontal space for relationship symbols
            padding_y = 60

            # Cache geometry to avoid repeated rect() calls
            node_sizes = {
                n: (item_map[n].rect().width(), item_map[n].rect().height())
                for n in comp_nodes
            }

            # Calculate total component height to center it vertically
            layer_heights = []
            max_comp_height = 0
            for r in sorted_ranks:
                h = sum(node_sizes[n][1] + padding_y for n in layers[r]) - padding_y
                layer_heights.append(h)
                max_comp_height = max(max_comp_height, h)

            current_x = 100
            for i, r in enumerate(sorted_ranks):
                nodes = layers[r]
                max_w = max(node_sizes[n][0] for n in nodes)

                # Starting Y to center this layer relative to the component
                layer_h = layer_heights[i]
                start_y = current_y_offset + (max_comp_height - layer_h) / 2

                local_y = start_y
                for name in nodes:
                    item = item_map[name]
                    item.setPos(current_x, local_y)
                    local_y += node_sizes[name][1] + padding_y

                current_x += max_w + padding_x

            current_y_offset += max_comp_height + 150 # Gap between subgraphs

        self.scene.update_scene_rect()
        if self.scene.items():
            QTimer.singleShot(0, self._center_view_deferred)

    def toggle_panel(self, checked):
        if checked:
            self.property_panel.show()
            self.property_panel.raise_()
            self._update_panel_geometry()
        else:
            self.property_panel.hide()
        
    def toggle_details(self, checked):
        icon_name = 'fa5s.eye' if checked else 'fa5s.eye-slash'
        self.show_details_action.setIcon(qta.icon(icon_name, color='#555555'))
        self.update_scene_items(ERDTableItem, 'show_columns', checked)

    def toggle_types(self, checked):
        self.update_scene_items(ERDTableItem, 'show_types', checked)
        
    def save_erd(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save ERD State", "", "ERD Files (*.erd)")
        if not file_path:
            return
            
        state = {
            "version": 1,
            "schema_data": self.schema_data,
            "positions": {}
        }
        
        for full_name, item in self.scene.tables.items():
            pos = item.pos()
            state["positions"][full_name] = {"x": pos.x(), "y": pos.y()}
            
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save ERD: {str(e)}")

    def load_erd_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open ERD State", "", "ERD Files (*.erd)")
        if not file_path:
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
                
            if "schema_data" in state:
                self.schema_data = state["schema_data"]
                self.scene.clear()
                self.undo_stack.clear()
                self.scene.tables = {}
                self.load_schema()
                
                # Restore positions
                positions = state.get("positions", {})
                for full_name, pos_data in positions.items():
                    if full_name in self.scene.tables:
                        item = self.scene.tables[full_name]
                        item.setPos(pos_data["x"], pos_data["y"])
                        

                # Update bounds and center
                self.scene.update_scene_rect()
                if self.scene.items():
                    QTimer.singleShot(0, self._center_view_deferred)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load ERD: {str(e)}")

    def save_as_image(self, ext="png"):
        filter_str = ""
        if ext == "svg":
            filter_str = "SVG Vector (*.svg)"
        elif ext == "pdf":
            filter_str = "PDF Document (*.pdf)"
        else:
            filter_str = "PNG Image (*.png);;JPG Image (*.jpg)"
            
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, 
            f"Export ERD Diagram as {ext.upper()}", 
            "", 
            filter_str
        )
        if not file_path:
            return
            
        # Adjust scene rect to bounding rect of all items
        local_rect = self.scene.itemsBoundingRect()
        if local_rect.isNull() or local_rect.width() <= 0 or local_rect.height() <= 0:
            QMessageBox.warning(self, "Empty Diagram", "The diagram is empty or invalid.")
            return

        items_rect = local_rect.adjusted(-50, -50, 50, 50)
        
        try:
            if file_path.endswith('.svg'):
                generator = QSvgGenerator()
                generator.setFileName(file_path)
                generator.setSize(QSize(int(items_rect.width()), int(items_rect.height())))
                generator.setViewBox(items_rect)
                generator.setTitle("Database ERD Diagram")
                generator.setDescription("Generated by DB Explorer")
                
                painter = QPainter()
                painter.begin(generator)
                self.scene.render(painter, QRectF(0, 0, items_rect.width(), items_rect.height()), items_rect)
                painter.end()
                
            elif file_path.endswith('.pdf'):
                printer = QPdfWriter(file_path)
                printer.setPageSize(QPageSize(QSize(int(items_rect.width()), int(items_rect.height()))))
                printer.setResolution(300)
                
                painter = QPainter()
                painter.begin(printer)
                self.scene.render(painter, QRectF(0, 0, printer.width(), printer.height()), items_rect)
                painter.end()
                
            else:
                # High quality export logic for PNG/JPG
                scale_factor = 2.0  # 2x scale for higher resolution
                w = int(items_rect.width() * scale_factor)
                h = int(items_rect.height() * scale_factor)
                
                # Limit max size to avoid OOM or Paint Engine failure
                MAX_DIM = 16000
                if w > MAX_DIM or h > MAX_DIM:
                     scale_factor = min(MAX_DIM / items_rect.width(), MAX_DIM / items_rect.height())
                     w = int(items_rect.width() * scale_factor)
                     h = int(items_rect.height() * scale_factor)
                
                img = QPixmap(w, h)
                if img.isNull():
                     QMessageBox.critical(self, "Error", "Failed to create image buffer (Out of Memory?).")
                     return

                # Transparent background for PNG, White for JPG
                if file_path.endswith('.png'):
                    img.fill(Qt.GlobalColor.transparent)
                else:
                    img.fill(Qt.GlobalColor.white)
                
                painter = QPainter(img)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                
                painter.scale(scale_factor, scale_factor)
                self.scene.render(painter, QRectF(0, 0, items_rect.width(), items_rect.height()), items_rect)
                painter.end()
                img.save(file_path)
                
            QMessageBox.information(self, "Success", f"ERD successfully exported to {file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export diagram: {str(e)}")

    def on_search_text_changed(self, text):
        if hasattr(self, 'scene') and self.scene:
            self.scene.apply_search_filter(text)

    def on_search_return_pressed(self):
        text = self.search_input.text()
        if hasattr(self, 'scene') and self.scene:
            item = self.scene.find_table_item(text)
            if item:
                self.view.centerOn(item)
                # Optional: Select it too
                self.scene.clearSelection()
                item.setSelected(True)

    def update_scene_items(self, item_type, attribute, value):
        """
        Updates a specific attribute for all items of a given type in the scene.
        """
        for item in self.scene.items():
            if isinstance(item, item_type):
                setattr(item, attribute, value)
                item.update_geometry()
                item.update()
