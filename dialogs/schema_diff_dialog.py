import json
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTabWidget, QWidget, QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem, QTextEdit, QFrame, QMessageBox,
    QHeaderView, QApplication
)
import qtawesome as qta

import db
from workers.schema_diff_worker import SchemaDiffWorker


class SchemaDiffDialog(QDialog):
    """
    Visual Cross-Source Schema Compare & Diff Tool.
    Compares tables, columns, and data types between any two databases/schemas
    and generates executable DDL migration scripts.
    """

    def __init__(self, manager, parent=None):
        super().__init__(parent or manager)
        self.manager = manager
        self.diff_result = None
        self.generated_sql = ""

        self.setWindowTitle("Cross-Source Schema Compare & Diff Tool")
        self.setMinimumSize(980, 680)

        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._apply_styles()
        self._setup_ui()
        self._load_connection_dropdowns()

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel#dialogTitle {
                font-size: 18px;
                font-weight: 700;
                color: #0f172a;
            }
            QLabel#dialogSubtitle {
                font-size: 12px;
                color: #64748b;
            }
            QGroupBox {
                font-weight: 600;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                margin-top: 6px;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                color: #1e293b;
            }
            QComboBox:hover {
                border-color: #0284c7;
            }
            QPushButton#compareBtn {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: 600;
                font-size: 13px;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton#compareBtn:hover {
                background-color: #0369a1;
            }
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f1f5f9;
                color: #475569;
                font-weight: 600;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #0284c7;
                border-bottom: 2px solid #0284c7;
            }
            QTreeWidget, QTableWidget {
                border: none;
                background-color: #ffffff;
                gridline-color: #f1f5f9;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #334155;
                font-weight: 600;
                border-bottom: 1px solid #e2e8f0;
                padding: 6px;
            }
        """)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header
        title_label = QLabel("Cross-Source Schema Compare & Diff Tool", self)
        title_label.setObjectName("dialogTitle")
        subtitle_label = QLabel("Compare structures, column data types, and generate DDL migration scripts between schemas.", self)
        subtitle_label.setObjectName("dialogSubtitle")

        main_layout.addWidget(title_label)
        main_layout.addWidget(subtitle_label)

        # Selection Bar (Source vs Target)
        sel_layout = QHBoxLayout()
        sel_layout.setSpacing(12)

        # Source Box
        src_box = QVBoxLayout()
        src_box.addWidget(QLabel("<b>Source Schema (Origin)</b>", self))
        self.src_conn_combo = QComboBox(self)
        self.src_conn_combo.currentIndexChanged.connect(self._on_src_conn_changed)
        self.src_schema_combo = QComboBox(self)

        src_box.addWidget(self.src_conn_combo)
        src_box.addWidget(self.src_schema_combo)
        sel_layout.addLayout(src_box)

        # VS Label
        vs_label = QLabel("⚡ VS ⚡", self)
        vs_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #0284c7;")
        vs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sel_layout.addWidget(vs_label)

        # Target Box
        tgt_box = QVBoxLayout()
        tgt_box.addWidget(QLabel("<b>Target Schema (Destination)</b>", self))
        self.tgt_conn_combo = QComboBox(self)
        self.tgt_conn_combo.currentIndexChanged.connect(self._on_tgt_conn_changed)
        self.tgt_schema_combo = QComboBox(self)

        tgt_box.addWidget(self.tgt_conn_combo)
        tgt_box.addWidget(self.tgt_schema_combo)
        sel_layout.addLayout(tgt_box)

        # Action Compare Button
        self.compare_btn = QPushButton("Compare Schemas", self)
        self.compare_btn.setObjectName("compareBtn")
        self.compare_btn.setIcon(qta.icon("fa5s.balance-scale", color="white"))
        self.compare_btn.clicked.connect(self._run_schema_compare)
        sel_layout.addWidget(self.compare_btn, 0, Qt.AlignmentFlag.AlignBottom)

        main_layout.addLayout(sel_layout)

        # Summary Header Badge Cards
        card_layout = QHBoxLayout()
        card_layout.setSpacing(12)

        self.card_matched = self._create_summary_card("Matched Objects", "0", "#10b981")
        self.card_missing = self._create_summary_card("Missing in Target", "0", "#ef4444")
        self.card_mismatch = self._create_summary_card("Type/Schema Mismatches", "0", "#f59e0b")

        card_layout.addWidget(self.card_matched)
        card_layout.addWidget(self.card_missing)
        card_layout.addWidget(self.card_mismatch)
        main_layout.addLayout(card_layout)

        # Tabs Widget
        self.tabs = QTabWidget(self)

        # Tab 1: Visual Diff Tree
        self.tab_tree = QWidget()
        tree_layout = QVBoxLayout(self.tab_tree)
        tree_layout.setContentsMargins(8, 8, 8, 8)

        self.diff_tree = QTreeWidget(self.tab_tree)
        self.diff_tree.setHeaderLabels(["Object Name", "Source Type", "Target Type", "Diff Classification"])
        self.diff_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tree_layout.addWidget(self.diff_tree)
        self.tabs.addTab(self.tab_tree, qta.icon("fa5s.sitemap", color="#0284c7"), "Side-by-Side Diff Tree")

        # Tab 2: Column Inspector Table
        self.tab_cols = QWidget()
        col_layout = QVBoxLayout(self.tab_cols)
        col_layout.setContentsMargins(8, 8, 8, 8)

        self.col_table = QTableWidget(self.tab_cols)
        self.col_table.setColumnCount(5)
        self.col_table.setHorizontalHeaderLabels(["Table Name", "Column Name", "Source Type", "Target Type", "Diff Status"])
        self.col_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        col_layout.addWidget(self.col_table)
        self.tabs.addTab(self.tab_cols, qta.icon("fa5s.table", color="#0284c7"), "Detailed Column Inspector")

        # Tab 3: Migration DDL Script
        self.tab_sql = QWidget()
        sql_layout = QVBoxLayout(self.tab_sql)
        sql_layout.setContentsMargins(8, 8, 8, 8)

        self.sql_editor = QTextEdit(self.tab_sql)
        self.sql_editor.setReadOnly(True)
        self.sql_editor.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                background-color: #0f172a;
                color: #38bdf8;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        sql_layout.addWidget(self.sql_editor)

        # SQL Actions Bar
        sql_btn_layout = QHBoxLayout()
        self.copy_sql_btn = QPushButton("Copy SQL Script", self.tab_sql)
        self.copy_sql_btn.setIcon(qta.icon("fa5s.copy", color="#334155"))
        self.copy_sql_btn.clicked.connect(self._copy_sql_script)

        self.open_worksheet_btn = QPushButton("Open in SQL Worksheet", self.tab_sql)
        self.open_worksheet_btn.setIcon(qta.icon("fa5s.terminal", color="#0284c7"))
        self.open_worksheet_btn.clicked.connect(self._open_in_worksheet)

        sql_btn_layout.addStretch()
        sql_btn_layout.addWidget(self.copy_sql_btn)
        sql_btn_layout.addWidget(self.open_worksheet_btn)
        sql_layout.addLayout(sql_btn_layout)

        self.tabs.addTab(self.tab_sql, qta.icon("fa5s.code", color="#0284c7"), "DDL Migration Script (SQL)")

        main_layout.addWidget(self.tabs)

        # Bottom Close Button
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(close_btn)
        main_layout.addLayout(bottom_layout)

    def _create_summary_card(self, title: str, count: str, color: str) -> QFrame:
        card = QFrame(self)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border-left: 4px solid {color};
                border: 1px solid #e2e8f0;
                border-left-width: 4px;
                border-left-color: {color};
                border-radius: 6px;
                padding: 8px 12px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        lbl_title = QLabel(title, card)
        lbl_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b;")
        lbl_count = QLabel(count, card)
        lbl_count.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {color};")
        card.lbl_count = lbl_count

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_count)
        return card

    def _load_connection_dropdowns(self):
        try:
            hierarchy = db.get_hierarchy_data()
            connections = []

            for type_item in hierarchy:
                for group_item in type_item.get("usf_connection_groups", []):
                    for conn in group_item.get("usf_connections", []):
                        connections.append(conn)

            self.src_conn_combo.blockSignals(True)
            self.tgt_conn_combo.blockSignals(True)
            self.src_conn_combo.clear()
            self.tgt_conn_combo.clear()

            for conn in connections:
                display_name = f"{conn.get('name')} ({conn.get('db_type', 'postgres').upper()})"
                self.src_conn_combo.addItem(display_name, conn)
                self.tgt_conn_combo.addItem(display_name, conn)

            self.src_conn_combo.blockSignals(False)
            self.tgt_conn_combo.blockSignals(False)

            if connections:
                self._on_src_conn_changed(0)
                if len(connections) > 1:
                    self.tgt_conn_combo.setCurrentIndex(1)
                self._on_tgt_conn_changed(self.tgt_conn_combo.currentIndex())
        except Exception as e:
            print(f"Notice: error loading connection dropdowns in SchemaDiffDialog: {e}")

    def _on_src_conn_changed(self, index):
        conn_data = self.src_conn_combo.itemData(index)
        self._populate_schemas(conn_data, self.src_schema_combo)

    def _on_tgt_conn_changed(self, index):
        conn_data = self.tgt_conn_combo.itemData(index)
        self._populate_schemas(conn_data, self.tgt_schema_combo)

    def _populate_schemas(self, conn_data, combo):
        combo.clear()
        if not conn_data:
            return

        db_type = (conn_data.get("db_type") or "postgres").lower()
        if "sqlite" in db_type:
            combo.addItem("main", "main")
        else:
            schemas = db.get_postgres_available_schemas(conn_data)
            if not schemas:
                schemas = ["public"]
            for s in schemas:
                combo.addItem(s, s)

    def _run_schema_compare(self):
        src_conn = self.src_conn_combo.itemData(self.src_conn_combo.currentIndex())
        src_schema = self.src_schema_combo.currentText()
        tgt_conn = self.tgt_conn_combo.itemData(self.tgt_conn_combo.currentIndex())
        tgt_schema = self.tgt_schema_combo.currentText()

        if not src_conn or not tgt_conn:
            QMessageBox.warning(self, "Invalid Selection", "Please select valid Source and Target connections.")
            return

        self.compare_btn.setEnabled(False)
        self.compare_btn.setText("Comparing...")

        worker = SchemaDiffWorker(src_conn, src_schema, tgt_conn, tgt_schema)
        worker.signals.finished.connect(self._on_compare_finished)
        worker.signals.error.connect(self._on_compare_error)
        self.manager.thread_pool.start(worker)

    def _on_compare_finished(self, result):
        self.compare_btn.setEnabled(True)
        self.compare_btn.setText("Compare Schemas")

        diff = result.get("diff_result", {})
        self.diff_result = diff
        self.generated_sql = result.get("ddl_script", "")

        # 1. Update Cards
        self.card_matched.lbl_count.setText(str(diff.get("matched_count", 0)))
        self.card_missing.lbl_count.setText(str(diff.get("missing_target_count", 0)))
        self.card_mismatch.lbl_count.setText(str(diff.get("mismatch_count", 0)))

        # 2. Populate Diff Tree
        self._populate_diff_tree(diff)

        # 3. Populate Column Inspector Table
        self._populate_col_table(diff)

        # 4. Populate SQL Script Editor
        self.sql_editor.setPlainText(self.generated_sql)

        self.manager.status.showMessage("Schema comparison finished successfully.", 4000)

    def _on_compare_error(self, err_msg):
        self.compare_btn.setEnabled(True)
        self.compare_btn.setText("Compare Schemas")
        QMessageBox.critical(self, "Comparison Error", f"Failed to compare schemas:\n{err_msg}")

    def _populate_diff_tree(self, diff: dict):
        self.diff_tree.clear()
        tbl_icon = qta.icon("fa5s.table", color="#0284c7")
        col_icon = qta.icon("fa5s.columns", color="#64748b")

        for tbl_diff in diff.get("table_diffs", []):
            tbl_name = tbl_diff["table_name"]
            tbl_status = tbl_diff["status"]

            tbl_item = QTreeWidgetItem(self.diff_tree)
            tbl_item.setText(0, tbl_name)
            tbl_item.setIcon(0, tbl_icon)
            tbl_item.setText(3, tbl_status)

            if tbl_status == "MATCH":
                tbl_item.setForeground(3, QColor("#10b981"))
            elif "MISSING" in tbl_status:
                tbl_item.setForeground(3, QColor("#ef4444"))
            else:
                tbl_item.setForeground(3, QColor("#f59e0b"))

            col_diffs = tbl_diff.get("column_diffs", [])
            for c_diff in col_diffs:
                col_item = QTreeWidgetItem(tbl_item)
                col_item.setText(0, f"  {c_diff['column_name']}")
                col_item.setIcon(0, col_icon)
                col_item.setText(1, c_diff.get("source_type", "-"))
                col_item.setText(2, c_diff.get("target_type", "-"))
                col_item.setText(3, c_diff["status"])

                if c_diff["status"] == "MATCH":
                    col_item.setForeground(3, QColor("#10b981"))
                elif "MISSING" in c_diff["status"]:
                    col_item.setForeground(3, QColor("#ef4444"))
                else:
                    col_item.setForeground(3, QColor("#f59e0b"))

            tbl_item.setExpanded(True)

    def _populate_col_table(self, diff: dict):
        rows = []
        for tbl_diff in diff.get("table_diffs", []):
            tbl_name = tbl_diff["table_name"]
            for c_diff in tbl_diff.get("column_diffs", []):
                rows.append((
                    tbl_name,
                    c_diff["column_name"],
                    c_diff.get("source_type", "-"),
                    c_diff.get("target_type", "-"),
                    c_diff["status"]
                ))

        self.col_table.setRowCount(len(rows))
        for row_idx, r_data in enumerate(rows):
            for col_idx, val in enumerate(r_data):
                item = QTableWidgetItem(str(val))
                if col_idx == 4:
                    if val == "MATCH":
                        item.setForeground(QColor("#10b981"))
                    elif "MISSING" in val:
                        item.setForeground(QColor("#ef4444"))
                    else:
                        item.setForeground(QColor("#f59e0b"))
                self.col_table.setItem(row_idx, col_idx, item)

    def _copy_sql_script(self):
        script = self.sql_editor.toPlainText()
        if script:
            QApplication.clipboard().setText(script)
            self.manager.status.showMessage("DDL Migration Script copied to clipboard!", 3000)

    def _open_in_worksheet(self):
        script = self.sql_editor.toPlainText()
        if script and hasattr(self.manager.main_window, "open_new_worksheet"):
            tgt_conn = self.tgt_conn_combo.itemData(self.tgt_conn_combo.currentIndex())
            self.manager.main_window.open_new_worksheet(conn_data=tgt_conn, initial_sql=script)
            self.accept()
