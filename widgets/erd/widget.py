import qtawesome as qta


from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QFileDialog, QMessageBox, QDialog,
    QToolButton, QLineEdit, QInputDialog,
    QFrame, QLabel, QProgressBar, QStackedWidget
)
from PySide6.QtGui import QAction, QTransform, QColor, QUndoStack
from PySide6.QtCore import Qt, QSize, QTimer, QPointF

from widgets.erd.items.table_item import ERDTableItem
from widgets.erd.items.connection_item import ERDConnectionItem
from widgets.erd.items.note_item import ERDNoteItem
from widgets.erd.items.entity_item import ERDEntityItem
from widgets.erd.items.weak_entity_item import ERDWeakEntityItem
from widgets.erd.items.attribute_item import ERDAttributeItem
from widgets.erd.items.relationship_diamond_item import ERDRelationshipDiamondItem
from widgets.erd.items.subject_area_item import ERDSubjectAreaItem
from widgets.erd.scene import ERDScene
from widgets.erd.view import ERDView
from widgets.erd.property_panel import PropertyPanel
from widgets.erd.palette import ERDPalette
from widgets.erd.dialogs import TableDesignerDialog, RelationDesignerDialog
from ui.components import SearchBox
from widgets.erd.commands import AddTableCommand, AddConnectionCommand, AddNoteCommand
from widgets.erd.model import DEFAULT_SCHEMA, normalize_entity
from widgets.erd.sql_generator import SQLPreviewDialog, generate_sql_script
from widgets.erd.layout_engine import auto_layout as _auto_layout
from widgets.erd.serialization import (
    serialize_view_state as _serialize_view_state_fn,
    restore_view_state as _restore_view_state_fn,
    create_free_item_from_state as _create_free_item_from_state_fn,
    serialize_free_item as _serialize_free_item_fn,
    save_erd as _save_erd,
    load_erd_file as _load_erd_file,
    save_as_image as _save_as_image,
)
from workers.connection_workers import AvailableSchemasWorker



# NOTE: This file exceeds the 500-line soft limit because ERDWidget is the
# central Qt widget coordinator: it owns the toolbar, scene, view, palette,
# property panel, loading overlay, schema loading, event filtering, and all
# the high-level action slots that tie these subsystems together.  All
# extractable logic (SQL generation, layout, serialisation) has been moved to
# dedicated modules.  What remains are exclusively thin Qt lifecycle methods
# (≤ 30 lines each) that cannot be meaningfully separated without introducing
# artificial indirection.
class ERDWidget(QWidget):
    def __init__(self, schema_data, parent=None, loading=False, conn_data=None):
        super().__init__(parent)
        self.schema_data = schema_data
        self._loading = loading
        self.conn_data = conn_data
        self.notes_data = []
        self.view_state_data = None
        self.undo_stack = QUndoStack(self)
        self._available_schemas_cache = None
        self._schema_worker = None
        self._drop_item_data_resolver = None
        self.initUI()
        self._start_schema_prefetch()
        
    _TOOLBAR_STYLE = """
        QToolBar {
            background-color: #ECEFF3;
            border-bottom: 1px solid #C9CFD8;
            spacing: 6px;
            padding: 3px 6px;
        }
        QToolButton {
            padding: 2px 8px;
            border: 1px solid #b9b9b9;
            background-color: #ffffff;
            border-radius: 4px;
            min-width: 14px;
            min-height: 24px;
        }
        QToolButton:hover { background-color: #e8e8e8; border-color: #9c9c9c; }
        QToolButton:pressed { background-color: #dcdcdc; }
    """

    def initUI(self) -> None:
        """Assemble the main layout: toolbar, content area, and initial data load."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(16, 16))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.setStyleSheet(self._TOOLBAR_STYLE)
        self._build_toolbar_file_export_group()
        layout.addWidget(self.toolbar)
        self._build_content_area(layout)
        self.load_schema()
        self.auto_layout()
        self._build_toolbar_view_edit_group()

    def _build_toolbar_file_export_group(self) -> None:
        """Add file open/save and export actions to the toolbar."""
        open_action = QAction(qta.icon('fa5s.folder-open', color='#555555'), "Open ERD (.erd)", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.load_erd_file)
        self.toolbar.addAction(open_action)
        save_action = QAction(qta.icon('fa5s.save', color='#555555'), "Save ERD (.erd)", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_erd)
        self.toolbar.addAction(save_action)
        self.toolbar.addSeparator()
        export_png = QAction(qta.icon('fa5s.image', color='#555555'), "Export to PNG", self)
        export_png.triggered.connect(lambda: self.save_as_image("png"))
        self.toolbar.addAction(export_png)
        export_svg = QAction(qta.icon('fa5s.vector-square', color='#555555'), "Export to SVG", self)
        export_svg.triggered.connect(lambda: self.save_as_image("svg"))
        self.toolbar.addAction(export_svg)
        export_pdf = QAction(qta.icon('fa5s.file-pdf', color='#555555'), "Export to PDF", self)
        export_pdf.triggered.connect(lambda: self.save_as_image("pdf"))
        self.toolbar.addAction(export_pdf)

    def _build_content_area(self, layout: QVBoxLayout) -> None:
        """Build scene, view, palette, canvas stack, and property panel."""
        self.scene = ERDScene(self)
        self.scene.undo_stack = self.undo_stack
        self.view = ERDView(self.scene, self)
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        self.palette = ERDPalette(self)
        content_layout.addWidget(self.palette)
        self.view_container = QWidget()
        self.view_layout = QVBoxLayout(self.view_container)
        self.view_layout.setContentsMargins(0, 0, 0, 0)
        self.view_layout.addWidget(self.view)
        self._canvas_stack = QStackedWidget()
        self._canvas_stack.addWidget(self._build_loading_overlay())
        self._canvas_stack.addWidget(self.view_container)
        self._canvas_stack.setCurrentIndex(0 if self._loading else 1)
        content_layout.addWidget(self._canvas_stack, 1)
        layout.addLayout(content_layout)
        self.property_panel = PropertyPanel(self.view, self.view_container)
        self.property_panel.hide()
        self.view_container.installEventFilter(self)
        self._build_floating_search()
        self.view.tree_item_dropped.connect(self._on_tree_item_dropped)

    def _build_toolbar_view_edit_group(self) -> None:
        """Add zoom, align, undo/redo, visibility, and advanced tool actions."""
        self.toolbar.addSeparator()
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
        reset_zoom_action.triggered.connect(self._zoom_to_fit)
        self.toolbar.addAction(reset_zoom_action)
        self.toolbar.addSeparator()
        align_action = QAction(qta.icon('fa5s.magic', color='#555555'), "Auto Align", self)
        align_action.setShortcut("Alt+Ctrl+L")
        align_action.triggered.connect(self.auto_layout)
        self.toolbar.addAction(align_action)
        self.undo_action = self.undo_stack.createUndoAction(self, "Undo")
        self.undo_action.setIcon(qta.icon('fa5s.undo', color='#555555'))
        self.undo_action.setShortcut("Ctrl+Z")
        self.toolbar.addAction(self.undo_action)
        self.redo_action = self.undo_stack.createRedoAction(self, "Redo")
        self.redo_action.setIcon(qta.icon('fa5s.redo', color='#555555'))
        self.redo_action.setShortcut("Ctrl+Y")
        self.toolbar.addAction(self.redo_action)
        self.toolbar.addSeparator()
        self._build_toolbar_visibility_group()
        self.toolbar.addSeparator()
        self._build_toolbar_advanced_group()

    def _build_toolbar_visibility_group(self) -> None:
        """Add show-details, show-types, and toggle-panel toggle actions."""
        self.show_details_action = QAction(qta.icon('fa5s.eye', color='#555555'), "Show Details", self)
        self.show_details_action.setShortcut("Alt+Ctrl+T")
        self.show_details_action.setCheckable(True)
        self.show_details_action.setChecked(True)
        self.show_details_action.triggered.connect(self.toggle_details)
        self.toolbar.addAction(self.show_details_action)
        self.show_types_action = QAction(qta.icon('mdi.label-outline', color='#555555'), "Show Data Types", self)
        self.show_types_action.setShortcut("Alt+Ctrl+D")
        self.show_types_action.setCheckable(True)
        self.show_types_action.setChecked(True)
        self.show_types_action.triggered.connect(self.toggle_types)
        self.toolbar.addAction(self.show_types_action)
        self.show_panel_action = QAction(qta.icon('mdi.card-text-outline', color='#555555'), "Toggle Panel", self)
        self.show_panel_action.setCheckable(True)
        self.show_panel_action.setChecked(False)
        self.show_panel_action.triggered.connect(self.toggle_panel)
        self.toolbar.addAction(self.show_panel_action)

    def _build_toolbar_advanced_group(self) -> None:
        """Add SQL generator and search toolbar buttons plus their keyboard shortcuts."""
        self.sql_btn = QToolButton()
        self.sql_btn.setIcon(qta.icon('fa5s.database', color='#555555'))
        self.sql_btn.setIconSize(QSize(16, 16))
        self.sql_btn.setFixedHeight(30)
        self.sql_btn.setMinimumWidth(26)
        self.sql_btn.setToolTip("Generate SQL Script (Alt+Ctrl+S)")
        self.sql_btn.clicked.connect(self.generate_forward_sql)
        self.toolbar.addWidget(self.sql_btn)
        self.sql_shortcut = QAction(self)
        self.sql_shortcut.setShortcut("Alt+Ctrl+S")
        self.sql_shortcut.triggered.connect(self.generate_forward_sql)
        self.addAction(self.sql_shortcut)
        self.search_btn = QToolButton()
        self.search_btn.setIcon(qta.icon('fa5s.search', color='#555555'))
        self.search_btn.setIconSize(QSize(16, 16))
        self.search_btn.setFixedHeight(30)
        self.search_btn.setMinimumWidth(26)
        self.search_btn.setToolTip("Search (Ctrl+F)")
        self.search_btn.clicked.connect(self.toggle_search)
        self.toolbar.addWidget(self.search_btn)

    def _build_floating_search(self) -> None:
        """Create the floating search input overlay and its Ctrl+F shortcut."""
        self.search_input = SearchBox("Search...", self.view_container)
        self.search_input.setFixedHeight(28)
        self.search_input.setFixedWidth(220)
        self.search_input.hide()
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.search_input.returnPressed.connect(self.on_search_return_pressed)
        self.search_input.installEventFilter(self)
        search_action = QAction(self)
        search_action.setShortcut("Ctrl+F")
        search_action.triggered.connect(self.toggle_search)
        self.addAction(search_action)



    def resizeEvent(self, event):
        super().resizeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)

    def _zoom_to_fit(self):
        """Fit the entire diagram into the current viewport, keeping aspect ratio."""
        rect = self.scene.itemsBoundingRect()
        if not rect.isNull():
            padded = rect.adjusted(-50, -50, 50, 50)
            self.view.fitInView(padded, Qt.AspectRatioMode.KeepAspectRatio)
            self.view.viewport_changed.emit()

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
            self.search_input.clear()  # Optional: Clear search on close
        else:
            self._position_search_input()
            self.search_input.show()
            self.search_input.raise_()
            self.search_input.setFocus()

    def _position_search_input(self):
        """Anchor the floating search input to the top-right of the view container."""
        if not hasattr(self, 'search_input') or not hasattr(self, 'view_container'):
            return
        margin = 12
        x = self.view_container.width() - self.search_input.width() - margin
        y = margin
        self.search_input.move(max(margin, x), y)

    def eventFilter(self, obj, event):
        if obj == getattr(self, 'search_input', None) and event.type() == event.Type.FocusOut:
            if not self.search_input.text():
                self.toggle_search()
        elif hasattr(self, 'view_container') and obj == self.view_container and event.type() == event.Type.Resize:
            self._update_panel_geometry()
            if hasattr(self, 'search_input') and self.search_input.isVisible():
                self._position_search_input()
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
        dialects = ["postgresql", "sqlite", "generic"]
        dialect, ok = QInputDialog.getItem(self, "Select SQL Dialect", "Select target dialect:", dialects, 0, False)
        if ok and dialect:
            sql_script = generate_sql_script(self.schema_data, dialect=dialect)
            dialog = SQLPreviewDialog(sql_script, self)
            dialog.exec()

    def _create_default_entity(self, pos, name=None):
        table_name = name or self._suggest_entity_name("new_entity")
        columns = [{"name": "id", "type": "INTEGER", "pk": True, "nullable": False}]
        self.undo_stack.push(AddTableCommand(
            self,
            table_name,
            columns,
            pos,
            schema_name=DEFAULT_SCHEMA,
        ))

    def _create_entity_with_fk(self, pos):
        table_name = self._suggest_entity_name("new_entity_fk")
        columns = [
            {"name": "id", "type": "INTEGER", "pk": True, "nullable": False},
            {"name": "parent_id", "type": "INTEGER", "nullable": True, "fk": True},
        ]

        self.undo_stack.beginMacro("Add Entity With FK")
        self.undo_stack.push(AddTableCommand(
            self,
            table_name,
            columns,
            pos,
            schema_name=DEFAULT_SCHEMA,
            foreign_keys=[],
        ))
        self.undo_stack.endMacro()

    def _on_tree_item_dropped(self, view_pos) -> None:
        """Slot: handle a tree-item drag-drop onto the ERD canvas."""
        if self._drop_item_data_resolver is None:
            return
        item_data = self._drop_item_data_resolver()
        if not item_data or not item_data.get("table_name"):
            return
        table_name = item_data.get("table_name")
        schema_name = item_data.get("schema_name")
        full_name = f"{schema_name}.{table_name}" if schema_name else table_name
        if full_name in self.scene.tables:
            return
        scene_pos = self.view.mapToScene(view_pos.toPoint())
        self.undo_stack.push(AddTableCommand(
            self,
            table_name,
            item_data.get("columns", []),
            scene_pos,
            schema_name=schema_name,
            foreign_keys=item_data.get("foreign_keys", []),
            notes=item_data.get("notes", []),
        ))

    def _create_note_at(self, text, pos):
        self.undo_stack.push(AddNoteCommand(self, text, pos))

    def _suggest_entity_name(self, base="new_entity"):
        name = base
        counter = 1
        while f"public.{name}" in self.scene.tables:
            name = f"{base}_{counter}"
            counter += 1
        return name

    def _start_schema_prefetch(self):
        """Kick off a background thread to pre-fetch available schemas."""
        if self._schema_worker and self._schema_worker.isRunning():
            return
        self._schema_worker = AvailableSchemasWorker(self.conn_data, self.schema_data, self)
        self._schema_worker.schemas_ready.connect(self._on_schemas_ready)
        self._schema_worker.start()

    def _on_schemas_ready(self, schemas):
        """Slot: cache the schema list returned by the background worker."""
        self._available_schemas_cache = schemas

    def _get_available_schemas(self) -> list[str]:
        """Return sorted list of schema names. Uses pre-fetched cache when available."""
        if self._available_schemas_cache is not None:
            return self._available_schemas_cache
        schemas = {v.get('schema', DEFAULT_SCHEMA) for v in self.schema_data.values() if isinstance(v, dict)}
        schemas.discard('')
        result = sorted(schemas)
        if DEFAULT_SCHEMA not in result:
            result.insert(0, DEFAULT_SCHEMA)
        self._available_schemas_cache = result
        return result

    def _open_entity_dialog(self, pos, preset=None):
        preset = preset or {}
        preset.setdefault("table", self._suggest_entity_name())
        dialog = TableDesignerDialog(
            self,
            table_name=preset.get("table", ""),
            columns=preset.get("columns", []),
            schema_name=preset.get("schema", DEFAULT_SCHEMA),
            notes=preset.get("notes", []),
            available_schemas=self._get_available_schemas(),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, cols, schema = dialog.get_result()
            cmd = AddTableCommand(self, name, cols, pos, schema_name=schema)
            self.undo_stack.push(cmd)

    def _free_item_types(self) -> tuple:
        return (
            ERDNoteItem,
            ERDEntityItem,
            ERDWeakEntityItem,
            ERDAttributeItem,
            ERDRelationshipDiamondItem,
            ERDSubjectAreaItem,
        )

    def _serialize_free_item(self, item) -> dict | None:
        return _serialize_free_item_fn(item)

    def _serialize_view_state(self) -> dict:
        return _serialize_view_state_fn(self.scene, self._free_item_types())

    def _create_free_item_from_state(self, data: dict):
        return _create_free_item_from_state_fn(data, self.scene)

    def _restore_view_state(self, state: dict) -> None:
        _restore_view_state_fn(state, self.scene, self._free_item_types())

    # ------------------------------------------------------------------
    # Async loading overlay
    # ------------------------------------------------------------------

    def _build_loading_overlay(self):
        frame = QFrame()
        frame.setStyleSheet("QFrame { background: #f8f9fb; }")
        overlay_layout = QVBoxLayout(frame)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overlay_layout.setSpacing(14)

        spinner = QProgressBar()
        spinner.setRange(0, 0)
        spinner.setFixedWidth(240)
        spinner.setFixedHeight(5)
        spinner.setTextVisible(False)
        spinner.setStyleSheet("""
            QProgressBar {
                border: none;
                background: #e5e7eb;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: #1A73E8;
                border-radius: 3px;
            }
        """)

        title = QLabel("Building diagram\u2026")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "color: #1f2937; font-size: 14px; font-weight: 600; background: transparent;"
        )

        subtitle = QLabel("Reading database structure\u2026")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            "color: #6b7280; font-size: 10px; background: transparent;"
        )

        self._load_error_label = QLabel("")
        self._load_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_error_label.setWordWrap(True)
        self._load_error_label.setStyleSheet(
            "color: #DC2626; font-size: 10px; background: transparent;"
        )
        self._load_error_label.hide()

        overlay_layout.addWidget(spinner)
        overlay_layout.addWidget(title)
        overlay_layout.addWidget(subtitle)
        overlay_layout.addWidget(self._load_error_label)
        return frame

    def populate(self, schema_data):
        """Called by the async worker when the schema fetch completes."""
        self.schema_data = schema_data
        self.load_schema()
        self.auto_layout()
        self._canvas_stack.setCurrentIndex(1)

    def show_load_error(self, message):
        """Display an inline error on the loading overlay (worker failed)."""
        self._load_error_label.setText(f"\u26a0\ufe0f  {message}")
        self._load_error_label.show()

    # ------------------------------------------------------------------

    _GROUP_COLORS = [
        QColor("#E8F0FE"), QColor("#FCE8E6"), QColor("#E6F4EA"), QColor("#FEF7E0"),
        QColor("#F3E5F5"), QColor("#E0F7FA"), QColor("#FFF0E0"), QColor("#F0F0F0"),
    ]

    def _build_table_items(self) -> None:
        """Create ERDTableItem for each entry in schema_data and assign group colours."""
        for full_name, table_info in self.schema_data.items():
            info = normalize_entity(table_info)
            table_name = info.get('table', full_name)
            schema_name = info.get('schema', DEFAULT_SCHEMA)
            columns = info['columns']
            fk_cols = {fk['from'] for fk in info.get('foreign_keys', [])}
            for col in columns:
                if col['name'] in fk_cols:
                    col['fk'] = True
            table_item = ERDTableItem(table_name, columns, schema_name=schema_name)
            self.scene.addItem(table_item)
            self.scene.tables[full_name] = table_item
        self._assign_group_colors()

    def _assign_group_colors(self) -> None:
        """Colour-code connected table groups via DFS on FK adjacency."""
        adj: dict = {name: [] for name in self.schema_data.keys()}
        for full_name, table_info in self.schema_data.items():
            info = normalize_entity(table_info)
            for fk in info.get('foreign_keys', []):
                target = fk['table']
                if target in adj:
                    adj[full_name].append(target)
                    adj[target].append(full_name)
        visited: set = set()
        group_idx = 0
        for name in self.schema_data.keys():
            if name not in visited:
                component: list = []
                stack = [name]
                while stack:
                    curr = stack.pop()
                    if curr not in visited:
                        visited.add(curr)
                        component.append(curr)
                        stack.extend(adj[curr])
                color = self._GROUP_COLORS[group_idx % len(self._GROUP_COLORS)]
                for comp_name in component:
                    if comp_name in self.scene.tables:
                        self.scene.tables[comp_name].group_color = color
                group_idx += 1

    def _build_connections(self) -> None:
        """Create ERDConnectionItem for each FK relationship in schema_data."""
        for full_name, table_info in self.schema_data.items():
            info = normalize_entity(table_info)
            source_item = self.scene.tables.get(full_name)
            if not source_item:
                continue
            pk_cols = {col['name'] for col in info['columns'] if col.get('pk')}
            for fk in info.get('foreign_keys', []):
                target_item = self.scene.tables.get(fk['table'])
                if not target_item:
                    continue
                is_identifying = fk['from'] in pk_cols
                is_unique = (
                    fk.get("type") == "one-to-one"
                    or is_identifying
                    or any(
                        col['name'] == fk['from'] and col.get('unique')
                        for col in info['columns']
                    )
                )
                conn_item = ERDConnectionItem(
                    source_item, target_item,
                    fk['from'], fk['to'],
                    is_identifying=is_identifying,
                    is_unique=is_unique,
                    fk_meta=fk,
                )
                self.scene.addItem(conn_item)

    def load_schema(self) -> None:
        """Populate scene from schema_data: tables, group colours, and connections."""
        self._build_table_items()
        self._build_connections()
        self.scene.update_scene_rect()

    def auto_layout(self):
        """Delegate hierarchical layout to layout_engine and refresh view."""
        if not self.scene.tables:
            return
        _auto_layout(self.schema_data, self.scene.tables)
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
        
    def save_erd(self) -> None:
        """Delegate to serialization module."""
        _save_erd(self)

    def load_erd_file(self, file_path: str | None = None) -> None:
        """Delegate to serialization module."""
        _load_erd_file(self, file_path)

    def add_new_table(self):
        view_center = self.view.mapToScene(self.view.viewport().rect().center())
        self._open_entity_dialog(view_center, preset={"schema": DEFAULT_SCHEMA, "columns": [{"name": "id", "type": "INTEGER", "pk": True, "nullable": False}]})


    def add_new_relationship(self):
        if not self.scene.tables:
            QMessageBox.warning(self, "No Tables", "Add at least two tables to create a relationship.")
            return

        dialog = RelationDesignerDialog(self, tables=self.scene.tables)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            res = dialog.get_result()
            cmd = AddConnectionCommand(
                self, 
                res['source_table'], res['source_col'],
                res['target_table'], res['target_col'],
                res['relation_type']
            )
            self.undo_stack.push(cmd)

    def add_new_note(self):
        view_center = self.view.mapToScene(self.view.viewport().rect().center())
        self._create_note_at("Note", view_center)

    def status_message(self, msg):
        # Notify parent main window if possible
        parent = self.parent()
        while parent:
            if hasattr(parent, 'status'):
                parent.status.showMessage(msg, 3000)
                break
            parent = parent.parent()

    def update_scene_items(self, item_type, attr, value):
        for item in self.scene.items():
            if isinstance(item, item_type):
                setattr(item, attr, value)
                if hasattr(item, 'update_geometry'):
                    item.update_geometry()
                item.update()

    def save_as_image(self, ext: str = "png") -> None:
        """Delegate to serialization module."""
        _save_as_image(self, ext)

    def on_search_text_changed(self, text):
        if hasattr(self, 'scene') and self.scene:
            self.scene.apply_search_filter(text)
            if text.strip():
                item = self.scene.find_table_item(text)
                if item:
                    self.view.centerOn(item)

    def on_search_return_pressed(self):
        text = self.search_input.text()
        if hasattr(self, 'scene') and self.scene:
            item = self.scene.find_table_item(text)
            if item:
                self.view.centerOn(item)
                # Optional: Select it too
                self.scene.clearSelection()
                item.setSelected(True)
