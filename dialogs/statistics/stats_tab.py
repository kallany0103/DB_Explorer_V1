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

    def load_stats(self, cursor, query, params, append=False):
        """
        Executes a query and loads the results into the model as key-value pairs.
        Expects a query that returns a single row where columns are 'key' names.
        """
        try:
            if not append:
                self.model.removeRows(0, self.model.rowCount())
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
            
            if row:
                for col_name, value in zip(columns, row):
                    # Format column name: replace underscores with spaces and capitalize
                    pretty_name = col_name.replace('_', ' ').capitalize()
                    
                    item_name = QStandardItem(pretty_name)
                    item_value = QStandardItem(str(value) if value is not None else "-")
                    self.model.appendRow([item_name, item_value])
            else:
                self.model.appendRow([QStandardItem("No statistics available"), QStandardItem("")])
        except Exception as e:
            self.model.appendRow([QStandardItem("Error loading statistics"), QStandardItem(str(e))])

    def load_multi_row_stats(self, cursor, query, params, headers=None):
        """
        Loads multiple rows into the table if the statistics query returns a list.
        """
        try:
            self.model.removeRows(0, self.model.rowCount())
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            
            if headers:
                self.model.setHorizontalHeaderLabels(headers)
            else:
                self.model.setHorizontalHeaderLabels([c.replace('_', ' ').capitalize() for c in columns])
                
            rows = cursor.fetchall()
            for row in rows:
                items = [QStandardItem(str(c) if c is not None else "-") for c in row]
                self.model.appendRow(items)
                
            if not rows:
                self.model.appendRow([QStandardItem("No data found")])
        except Exception as e:
            self.model.appendRow([QStandardItem("Error"), QStandardItem(str(e))])
