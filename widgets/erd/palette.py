import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, 
    QListWidget, QListWidgetItem, QAbstractItemView
)
from PySide6.QtCore import Qt, QSize, QMimeData
from PySide6.QtGui import QDrag, QPixmap

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
                padding: 10px;
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
        self.list.setIconSize(QSize(24, 24))
        self.list.setSpacing(0)
        self.list.hide() # Initially closed
        
        # New Table Item
        table_item = QListWidgetItem(qta.icon('fa5s.table', color='#1A73E8'), "New Table")
        table_item.setData(Qt.ItemDataRole.UserRole, "table")
        self.list.addItem(table_item)
        
        # New Column Item
        column_item = QListWidgetItem(qta.icon('fa5s.columns', color='#34A853'), "New Column")
        column_item.setData(Qt.ItemDataRole.UserRole, "column")
        self.list.addItem(column_item)
        
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
