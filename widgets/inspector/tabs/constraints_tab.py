from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtGui import QStandardItemModel, QStandardItem
from widgets.inspector.properties_ui import PropertyTable

class ConstraintsTab(QWidget):
    def __init__(self, data):
        super().__init__()
        self.init_ui(data)

    def init_ui(self, data):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        table = PropertyTable()
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Name", "Type", "Definition"])
        
        constraints = data.get("constraints", [])
        for cons in constraints:
            items = [QStandardItem(str(cons.get("name", ""))),
                     QStandardItem(str(cons.get("type", ""))),
                     QStandardItem(str(cons.get("definition", "")))]
            model.appendRow(items)
        
        table.setModel(model)
        table.resizeColumnsToContents()
        layout.addWidget(table)
