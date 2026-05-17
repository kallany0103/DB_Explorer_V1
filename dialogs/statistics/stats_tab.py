# dialogs/properties/statistics/stats_tab.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QHeaderView, QLabel
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt

class StatisticsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        self.title_label = QLabel("Object Statistics")
        self.title_label.setObjectName("dialogSubtitle")
        self.layout.addWidget(self.title_label)
        
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Property", "Value"])
        
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.view.setAlternatingRowColors(True)
        
        self.layout.addWidget(self.view)

    def clear_stats(self):
        self.model.removeRows(0, self.model.rowCount())
        self.model.setHorizontalHeaderLabels(["Property", "Value"])

    def display_data(self, columns, rows, append=False):
        if not append:
            self.clear_stats()
            
        if rows:
            # If multiple rows, change to table view mode
            if len(rows) > 1:
                self.model.setHorizontalHeaderLabels([c.replace('_', ' ').capitalize() for c in columns])
                for row in rows:
                    items = [QStandardItem(str(val) if val is not None else "-") for val in row]
                    self.model.appendRow(items)
            else:
                # Single row: Key-Value mode
                row = rows[0]
                for col_name, value in zip(columns, row):
                    pretty_name = col_name.replace('_', ' ').capitalize()
                    item_name = QStandardItem(pretty_name)
                    item_value = QStandardItem(str(value) if value is not None else "-")
                    self.model.appendRow([item_name, item_value])
        else:
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
            self.model.appendRow([QStandardItem("Error"), QStandardItem(str(e))])
