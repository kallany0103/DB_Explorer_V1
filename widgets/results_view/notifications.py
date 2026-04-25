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
    tree.setAlternatingRowColors(False)
    tree.setIndentation(0)
    
    # Hide header
    tree.header().hide()
    
    model = QStandardItemModel(0, 1)
    tree.setModel(model)
    
    tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    
    tree.setStyleSheet(
        """
            QTreeView {
                border: none;
                background-color: #ffffff;
                alternate-background-color: #f8f9fa;
                font-size: 8pt;
                color: #333333;
            }
            QTreeView::item {
                padding: 10px 12px;
                border-bottom: 1px solid #eef0f2;
            }
        """
    )
    
    return tree

def add_connection_event(tree_view, conn_name):
    model = tree_view.model()
    if not isinstance(model, QStandardItemModel):
        return
        
    text_color = QColor("#111111")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    
    # Update existing connections that are still 'active' (no Deactive timestamp yet)
    for row in range(model.rowCount()):
        item = model.item(row, 0)
        if item and "Deactive:" not in item.text():
            current_text = item.text()
            new_text = f"{current_text} | Deactive: {now_str}"
            item.setText(new_text)

    # Add new active record (without 'Live')
    new_text = f"{conn_name}\nActive: {now_str}"
    conn_item = QStandardItem(new_text)
    conn_item.setForeground(text_color)
    
    model.insertRow(0, [conn_item])
