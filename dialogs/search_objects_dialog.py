from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
    QAbstractItemView, QMessageBox, QApplication
)
from PySide6.QtCore import Qt
import qtawesome as qta

class SearchObjectsDialog(QDialog):
    """
    Dialog for global object search across all PostgreSQL schemas.
    """
    def __init__(self, manager, conn_data, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.conn_data = conn_data
        self.setWindowTitle("Search Objects")
        self.resize(700, 500)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.setStyleSheet(self.manager._get_dialog_style())

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        title = QLabel("Search Database Objects")
        title.setObjectName("dialogTitle")
        subtitle = QLabel("Find tables, views, functions, and more across all schemas.")
        subtitle.setObjectName("dialogSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Search Bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Object name (supports % wildcards)...")
        self.search_input.returnPressed.connect(self.perform_search)
        
        self.search_btn = QPushButton("Search")
        self.search_btn.setObjectName("primaryButton")
        self.search_btn.setIcon(qta.icon("mdi.magnify", color="white"))
        self.search_btn.clicked.connect(self.perform_search)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)
        layout.addLayout(search_layout)

        # Results Table
        self.results_table = QTableWidget(0, 3)
        self.results_table.setHorizontalHeaderLabels(["Schema", "Name", "Type"])
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.itemDoubleClicked.connect(self.navigate_to_selected)
        
        layout.addWidget(self.results_table)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        self.goto_btn = QPushButton("Go to Object")
        self.goto_btn.setEnabled(False)
        self.goto_btn.clicked.connect(self.navigate_to_selected)
        
        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryButton")
        close_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.goto_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.results_table.itemSelectionChanged.connect(
            lambda: self.goto_btn.setEnabled(len(self.results_table.selectedItems()) > 0)
        )

    def perform_search(self):
        query_text = self.search_input.text().strip()
        if not query_text:
            return

        self.search_btn.setEnabled(False)
        self.search_btn.setText("Searching...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            results = self.manager.connection_actions.fetch_search_results(self.conn_data, query_text)
            self.results_table.setRowCount(0)
            
            if not results:
                print("DEBUG: Search returned no results.")
                return

            print(f"DEBUG: Processing {len(results)} search results.")
            for i, row_data in enumerate(results):
                try:
                    # Defensive check: ensure the resulting row has at least 3 columns
                    if not row_data or len(row_data) < 3:
                        print(f"WARNING: Skipping malformed row {i}: {row_data} (Len: {len(row_data) if row_data else 0})")
                        continue

                    row_idx = self.results_table.rowCount()
                    self.results_table.insertRow(row_idx)
                    
                    # Convert to string safely
                    schema_str = str(row_data[0]) if row_data[0] is not None else ""
                    name_str = str(row_data[1]) if row_data[1] is not None else ""
                    type_str = str(row_data[2]) if row_data[2] is not None else "Other"

                    schema_item = QTableWidgetItem(schema_str)
                    name_item = QTableWidgetItem(name_str)
                    type_item = QTableWidgetItem(type_str)
                    
                    # Add icons based on type
                    icon_map = {
                        "Table": "mdi.table",
                        "View": "mdi.eye-outline",
                        "Function": "mdi.function-variant",
                        "Index": "mdi.format-list-bulleted",
                        "Sequence": "mdi.numeric",
                        "Foreign Table": "mdi.table-network",
                        "Materialized View": "mdi.eye-settings"
                    }
                    icon_str = icon_map.get(type_str, "mdi.database-outline")
                    name_item.setIcon(qta.icon(icon_str, color="#0078d4"))
                    
                    self.results_table.setItem(row_idx, 0, schema_item)
                    self.results_table.setItem(row_idx, 1, name_item)
                    self.results_table.setItem(row_idx, 2, type_item)
                except Exception as row_exc:
                    print(f"CRITICAL: Failed to process row {i} [{row_data}]: {row_exc}")
                    # Continue to next row instead of crashing the whole search
                    continue

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Search Error", f"Failed to perform search:\n{str(e)}")
        finally:
            self.search_btn.setEnabled(True)
            self.search_btn.setText("Search")
            QApplication.restoreOverrideCursor()

    def navigate_to_selected(self):
        selected_items = self.results_table.selectedItems()
        if not selected_items:
            return
        
        schema = self.results_table.item(selected_items[0].row(), 0).text()
        name = self.results_table.item(selected_items[0].row(), 1).text()
        obj_type = self.results_table.item(selected_items[0].row(), 2).text()
        
        self.manager.connection_actions.navigate_to_object(schema, name, obj_type)
