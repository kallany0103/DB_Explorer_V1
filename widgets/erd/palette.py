import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QSize, QMimeData
from PySide6.QtGui import QDrag

class ERDPalette(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.expanded_width = 140
        self.collapsed_width = 36
        self.setFixedWidth(self.collapsed_width)
        self.setStyleSheet("""
            ERDPalette {
                background-color: #f8f9fa;
                border-right: 1px solid #d1d5db;
            }
            QListWidget {
                border: none;
                background-color: transparent;
                outline: none;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #e5e7eb;
                color: #374151;
            }
            QListWidget::item:hover {
                background-color: #e5e7eb;
            }
            QListWidget::item:selected {
                background-color: #e8f0fe;
                color: #1a73e8;
                border-left: 3px solid #1a73e8;
            }
            QPushButton#headerBtn {
                text-align: left;
                font-weight: bold;
                padding: 8px;
                color: #374151;
                border: none;
                background: transparent;
            }
            QPushButton#headerBtn:hover {
                background: #e5e7eb;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        from PySide6.QtWidgets import QPushButton
        self.header_btn = QPushButton()
        self.header_btn.setObjectName("headerBtn")
        self.header_btn.setIcon(qta.icon('fa5s.chevron-right', color='#374151'))
        self.header_btn.clicked.connect(self.toggle_collapse)
        layout.addWidget(self.header_btn)
        
        self.list = QListWidget()
        self.list.setDragEnabled(True)
        self.list.setViewMode(QListWidget.ViewMode.ListMode)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.setWordWrap(True)
        self.list.setIconSize(QSize(24, 24))
        self.list.setSpacing(0)
        self.list.hide() # Initially closed
        
        def add_item(icon_name, text, role, height=42, icon_color='#5F6368'):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, role)
            item.setSizeHint(QSize(self.expanded_width - 12, height))
            self.list.addItem(item)
            
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 4, 8, 4)
            row_layout.setSpacing(8)

            icon_lbl = QLabel()
            icon_lbl.setPixmap(qta.icon(icon_name, color=icon_color).pixmap(22, 22))
            icon_lbl.setFixedSize(22, 22)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            text_lbl = QLabel(text)
            text_lbl.setWordWrap(True)
            text_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            text_lbl.setStyleSheet("color: #374151; font-size: 12px;")

            row_layout.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignTop)
            row_layout.addWidget(text_lbl, 1)
            self.list.setItemWidget(item, row)
            return item

        # New Entity Items
        add_item('fa5s.table', "New Entity", "table", 40, '#1A73E8')

        add_item('fa5s.link', "New Entity with FK", "table_fk", 46, '#1A73E8')
        
        # New Column Item
        add_item('fa5s.columns', "New Column", "column", 40, '#34A853')

        add_item('fa5s.sticky-note', "Note", "note", 36, '#D4A100')
        
        # Relationships
        add_item('mdi6.relation-one-to-one', "1-1 Relation", "relationship:one-to-one", 40)
        
        add_item('mdi6.relation-one-to-many', "1-M Relation", "relationship:one-to-many", 40)
        
        add_item('mdi6.relation-many-to-one', "M-1 Relation", "relationship:many-to-one", 40)
        
        add_item('mdi6.relation-many-to-many', "M-M Relation", "relationship:many-to-many", 40)
        
        layout.addWidget(self.list)
        layout.addStretch() # Push everything up
        
        # Custom drag handling to provide specific MIME data
        self.list.startDrag = self._start_drag

    def toggle_collapse(self):
        if self.list.isVisible():
            self.list.hide()
            self.setFixedWidth(self.collapsed_width)
            self.header_btn.setText("")
            self.header_btn.setIcon(qta.icon('fa5s.chevron-right', color='#374151'))
        else:
            self.list.show()
            self.setFixedWidth(self.expanded_width)
            self.header_btn.setText(" Components")
            self.header_btn.setIcon(qta.icon('fa5s.chevron-down', color='#374151'))

    def _start_drag(self, supported_actions):
        item = self.list.currentItem()
        if not item:
            return
            
        comp_type = item.data(Qt.ItemDataRole.UserRole)
        
        mime_data = QMimeData()
        mime_data.setData("application/x-erd-component", comp_type.encode('utf-8'))
        
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        
        # Optional: set a pixmap for the drag
        pixmap = item.icon().pixmap(32, 32)
        drag.setPixmap(pixmap)
        drag.setHotSpot(pixmap.rect().center())
        
        drag.exec(Qt.DropAction.CopyAction)
