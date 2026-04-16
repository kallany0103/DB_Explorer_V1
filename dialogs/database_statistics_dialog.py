from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QGridLayout, QPushButton, QFrame, QMessageBox, QApplication
)
from PySide6.QtCore import Qt
import qtawesome as qta

class DatabaseStatisticsDialog(QDialog):
    """
    Dialog showing an overview of database statistics.
    """
    def __init__(self, manager, conn_data, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.conn_data = conn_data
        self.setWindowTitle("Database Statistics")
        self.resize(500, 450)
        self.setStyleSheet(self.manager._get_dialog_style())

        self.init_ui()
        self.load_statistics()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Header
        title = QLabel(f"Statistics: {self.conn_data.get('database')}")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        # Stats Container
        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(15)
        
        # We'll populate this in load_statistics
        layout.addLayout(self.stats_grid)
        
        layout.addStretch()

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryButton")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _add_stat_row(self, row, icon_name, label_text, value_text):
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon(icon_name, color="#0078d4").pixmap(24, 24))
        
        name_label = QLabel(label_text)
        name_label.setStyleSheet("font-weight: 600; color: #374151;")
        
        val_label = QLabel(str(value_text))
        val_label.setStyleSheet("color: #111827; font-family: 'Consolas', monospace;")
        val_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.stats_grid.addWidget(icon_label, row, 0)
        self.stats_grid.addWidget(name_label, row, 1)
        self.stats_grid.addWidget(val_label, row, 2)

    def load_statistics(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            stats = self.manager.connection_actions.fetch_database_statistics(self.conn_data)
            
            # Clear grid (if needed)
            # Add rows
            self._add_stat_row(0, "mdi.database", "Database Size", stats.get('db_size', 'N/A'))
            
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet("color: #e5e7eb;")
            self.stats_grid.addWidget(line, 1, 0, 1, 3)

            self._add_stat_row(2, "mdi.folder-table", "Schemas", stats.get('schema_count', 0))
            self._add_stat_row(3, "mdi.table", "Tables", stats.get('table_count', 0))
            self._add_stat_row(4, "mdi.eye-outline", "Views", stats.get('view_count', 0))
            self._add_stat_row(5, "mdi.format-list-bulleted", "Indexes", stats.get('index_count', 0))
            self._add_stat_row(6, "mdi.function-variant", "Functions", stats.get('function_count', 0))
            self._add_stat_row(7, "mdi.numeric", "Sequences", stats.get('sequence_count', 0))
            
            line2 = QFrame()
            line2.setFrameShape(QFrame.Shape.HLine)
            line2.setStyleSheet("color: #e5e7eb;")
            self.stats_grid.addWidget(line2, 8, 0, 1, 3)
            
            self._add_stat_row(9, "mdi.account-multiple", "Active Sessions", stats.get('active_sessions', 0))

        except Exception as e:
            QMessageBox.critical(self, "Stats Error", f"Failed to load statistics:\n{str(e)}")
        finally:
            QApplication.restoreOverrideCursor()
