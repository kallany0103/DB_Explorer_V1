import qtawesome as qta
# from PyQt6.QtWidgets import (
#     QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea,
#     QFormLayout, QComboBox, QPushButton, QHBoxLayout,
#     QGraphicsDropShadowEffect
# )
# from PyQt6.QtCore import Qt, QSize
# from PyQt6.QtGui import QFont, QColor

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea,
    QFormLayout, QComboBox, QPushButton, QHBoxLayout,
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor

from widgets.erd.items.table_item import ERDTableItem
from widgets.erd.items.connection_item import ERDConnectionItem
from widgets.erd.commands import ChangeRelationTypeCommand


class PropertyPanel(QWidget):
    def __init__(self, view, parent=None):
        super().__init__(parent)
        self.view = view
        self.scene = view.scene()
        self.setFixedWidth(280)
        self.setStyleSheet("""
            PropertyPanel {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 8px;
            }
            QLabel {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            .panel-header {
                font-size: 14px;
                font-weight: bold;
                padding: 12px;
                background-color: transparent;
                border-bottom: 1px solid #e5e7eb;
            }
        """)
        
        # Add Drop Shadow for Overlay Floating Effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
        # Main layout (add small margins so border-radius draws safely)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Header label
        self.header_label = QLabel("Properties")
        self.header_label.setProperty("class", "panel-header")
        self.layout.addWidget(self.header_label)
        
        # Scroll area for dynamic content
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.content_widget)
        
        self.layout.addWidget(self.scroll_area)
        
        # Listen to selection changes
        self.scene.selectionChanged.connect(self.update_content)
        
        self.update_content()
        
    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    subitem = item.layout().takeAt(0)
                    if subitem.widget():
                        subitem.widget().deleteLater()
                item.layout().deleteLater()

    def sizeHint(self):
        # Dynamically calculate required height
        if not self.content_widget:
            return QSize(self.width(), 100)
            
        header_h = self.header_label.height()
        content_h = self.content_widget.sizeHint().height()
        
        # Pad significantly to ensure bottom items (especially combo boxes or last columns)
        # have plenty of breathing room to be scrolled and clicked
        return QSize(self.width(), header_h + content_h + 60)

    def update_content(self):
        self._clear_content()
        
        try:
            selected_items = self.scene.selectedItems()
        except RuntimeError:
            # The underlying C++ object is deleted (e.g. when scene is cleared during reload)
            return
        
        
        if len(selected_items) == 0:
            self.header_label.setText("Diagram Stats")
            self._render_empty_state()
        elif len(selected_items) == 1:
            item = selected_items[0]
            if isinstance(item, ERDTableItem):
                self.header_label.setText("Table Details")
                self._render_table_details(item)
            elif isinstance(item, ERDConnectionItem):
                self.header_label.setText("Relation Details")
                self._render_connection_details(item)
            else:
                self.header_label.setText("Properties")
        else:
            self.header_label.setText("Multiple Items")
            self._render_multi_selection(selected_items)

    def _render_empty_state(self):
        table_count = sum(1 for item in self.scene.items() if isinstance(item, ERDTableItem))
        conn_count = sum(1 for item in self.scene.items() if isinstance(item, ERDConnectionItem))
        
        form = QFormLayout()
        form.addRow("Tables:", QLabel(str(table_count)))
        form.addRow("Connections:", QLabel(str(conn_count)))
        self.content_layout.addLayout(form)
        
        layout_btn = QPushButton("Auto Layout")
        layout_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                background-color: #ffffff;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
            }
            QPushButton:pressed {
                background-color: #e5e7eb;
            }
        """)
        # Find ERDWidget to trigger auto layout
        parent_widget = self.view.parent()
        layout_btn.clicked.connect(lambda: parent_widget.auto_layout() if hasattr(parent_widget, "auto_layout") else None)
        self.content_layout.addWidget(layout_btn)

    def _render_table_details(self, table_item):
        form = QFormLayout()
        name_lbl = QLabel(table_item.table_name)
        name_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        form.addRow("Name:", name_lbl)
        if table_item.schema_name:
            form.addRow("Schema:", QLabel(table_item.schema_name))
        
        self.content_layout.addLayout(form)
        
        # Columns
        col_lbl = QLabel("Columns:")
        col_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.content_layout.addWidget(col_lbl)
        
        for col in table_item.columns:
            rfx = QHBoxLayout()
            icon_lbl = QLabel()
            if col.get('pk'):
                icon_lbl.setPixmap(qta.icon('fa5s.key', color='#F9AB00').pixmap(12,12))
            elif col.get('fk'):
                icon_lbl.setPixmap(qta.icon('fa5s.key', color='#1A73E8').pixmap(12,12))
            else:
                icon_lbl.setPixmap(qta.icon('fa5s.columns', color='#34A853').pixmap(12,12))
                
            rfx.addWidget(icon_lbl)
            rfx.addWidget(QLabel(col['name']))
            type_lbl = QLabel(col.get('type', ''))
            type_lbl.setStyleSheet("color: #70757A;")
            rfx.addWidget(type_lbl, 1, Qt.AlignmentFlag.AlignRight)
            
            w = QWidget()
            w.setLayout(rfx)
            w.setFixedHeight(24)
            rfx.setContentsMargins(0, 0, 0, 0)
            self.content_layout.addWidget(w)

    def _render_connection_details(self, conn_item):
        form = QFormLayout()
        s_name = conn_item.source_item.table_name
        t_name = conn_item.target_item.table_name
        s_text = f"{s_name}.{conn_item.source_col}" if conn_item.source_col else s_name
        t_text = f"{t_name}.{conn_item.target_col}" if conn_item.target_col else t_name

        form.addRow("Source:", QLabel(s_text))
        form.addRow("Target:", QLabel(t_text))
        if getattr(conn_item, "fk_meta", None):
            if conn_item.fk_meta.get("on_delete"):
                form.addRow("On Delete:", QLabel(conn_item.fk_meta.get("on_delete", "NO ACTION")))
            if conn_item.fk_meta.get("on_update"):
                form.addRow("On Update:", QLabel(conn_item.fk_meta.get("on_update", "NO ACTION")))
        self.content_layout.addLayout(form)
        
        self.content_layout.addWidget(QLabel("Relation Type:"))
        combo = QComboBox()
        # Ensure mapping of dropdown indexes to relation type keys
        type_keys = list(conn_item.RELATION_TYPES.keys())
        for key in type_keys:
            combo.addItem(conn_item.RELATION_TYPES[key]['label'])
            
        current_idx = type_keys.index(conn_item.relation_type) if conn_item.relation_type in type_keys else 0
        combo.setCurrentIndex(current_idx)
        
        def on_combo_changed(idx):
            new_type = type_keys[idx]
            cmd = ChangeRelationTypeCommand(conn_item, conn_item.relation_type, new_type)
            self.scene.undo_stack.push(cmd)
            
        combo.currentIndexChanged.connect(on_combo_changed)
        self.content_layout.addWidget(combo)

    def _render_multi_selection(self, selected_items):
        self.content_layout.addWidget(QLabel(f"Selected Items: {len(selected_items)}"))
