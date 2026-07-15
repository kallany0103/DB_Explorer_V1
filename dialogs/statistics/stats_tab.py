from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHeaderView, QLabel
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont
from PySide6.QtCore import Qt
from widgets.inspector.properties_ui import PropertyTable

class StatisticsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Property", "Value"])
        
        self.view = PropertyTable()
        self.view.setModel(self.model)
        
        # Adjust sizing for the properties tab format
        hh = self.view.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.view.setColumnWidth(0, 250)
        
        self.layout.addWidget(self.view)

    def clear_stats(self):
        self.model.removeRows(0, self.model.rowCount())
        self.model.setHorizontalHeaderLabels(["Property", "Value"])
        self.view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.view.setColumnWidth(0, 250)

    def display_data(self, columns, rows, append=False):
        if not append:
            self.clear_stats()
            
        if rows:
            # If multiple rows, change to generic table view mode
            if len(rows) > 1:
                if not append:
                    self.model.setHorizontalHeaderLabels([c.replace('_', ' ').capitalize() for c in columns])
                    hh = self.view.horizontalHeader()
                    for i in range(len(columns)):
                        hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                    if len(columns) > 0:
                        hh.setSectionResizeMode(len(columns) - 1, QHeaderView.ResizeMode.Stretch)
                
                for row in rows:
                    items = []
                    for val in row:
                        if isinstance(val, (int, float)) and not isinstance(val, bool):
                            display_val = f"{val:,}"
                        else:
                            display_val = str(val) if val is not None else "-"
                        item = QStandardItem(display_val)
                        items.append(item)
                    self.model.appendRow(items)
            else:
                # Single row: Key-Value mode
                row = rows[0]
                for col_name, value in zip(columns, row):
                    pretty_name = col_name.replace('_', ' ').capitalize()
                    
                    item_name = QStandardItem(pretty_name)
                    # Make property keys bold for readability
                    font = item_name.font()
                    font.setWeight(QFont.Weight.DemiBold)
                    item_name.setFont(font)
                    item_name.setForeground(Qt.GlobalColor.darkGray)
                    
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        display_val = f"{value:,}"
                    else:
                        display_val = str(value) if value is not None else "-"
                        
                    item_value = QStandardItem(display_val)
                    
                    self.model.appendRow([item_name, item_value])
        else:
            if not append:
                self.model.appendRow([QStandardItem("No statistics available"), QStandardItem("")])

    def load_stats(self, cursor, query, params=(), append=False):
        try:
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            self.display_data(columns, rows, append=append)
        except Exception as e:
            if not append:
                self.clear_stats()
            
            item_err_key = QStandardItem("Error")
            font = item_err_key.font()
            font.setWeight(600)
            item_err_key.setFont(font)
            item_err_key.setForeground(Qt.GlobalColor.red)
            
            self.model.appendRow([item_err_key, QStandardItem(str(e))])
