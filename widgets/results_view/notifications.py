from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import QTreeView, QAbstractItemView, QHeaderView
import datetime
from PySide6.QtGui import QColor

def create_notification_view():
    tree = QTreeView()
    tree.setObjectName("notification_list_view")
    tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    tree.setRootIsDecorated(False)
    tree.setAlternatingRowColors(True)
    
    model = QStandardItemModel(0, 2)
    model.setHorizontalHeaderLabels(["Active Connection", "Connection Time"])
    tree.setModel(model)
    
    header = tree.header()
    header.setFixedHeight(30)
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
    header.resizeSection(1, 160)
    header.setStretchLastSection(False)
    
    tree.setStyleSheet(
        """
            QTreeView {
                border: none;
                background-color: #ffffff;
                alternate-background-color: #f8f9fa;
                font-size: 9pt;
                color: #333333;
            }
            QTreeView::item {
                padding: 4px 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QHeaderView::section {
                background-color: #9FA6AF;
                color: #ffffff;
                padding: 2px 8px;
                border: none;
                border-right: 1px solid #B8BEC6;
                border-bottom: 1px solid #8B929B;
                font-weight: bold;
                font-size: 9pt;
                text-align: left;
            }
        """
    )
    
    return tree

def add_connection_event(tree_view, conn_name):
    model = tree_view.model()
    if not isinstance(model, QStandardItemModel):
        return
        
    secondary_color = QColor("#888888")
    
    # Mark all existing connections as deactivated
    for row in range(model.rowCount()):
        item = model.item(row, 0)
        if item and item.text().startswith("Connected:"):
            old_text = item.text().replace("Connected:", "").strip()
            item.setText(f"Deactivated: {old_text}")
            item.setForeground(secondary_color)
            
            time_item = model.item(row, 1)
            if time_item:
                time_item.setForeground(secondary_color)

    # Add new active connection record
    time_str = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    
    conn_item = QStandardItem(f"Connected: {conn_name}")
    time_item = QStandardItem(time_str)
    model.insertRow(0, [conn_item, time_item])
