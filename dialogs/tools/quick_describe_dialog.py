"""
dialogs/tools/quick_describe_dialog.py
Toad for Oracle-style Quick Describe (Ctrl+D).

Simple input form: Object Type / Owner / Name -> Describe.
Delegates to ObjectDescribeDialog (F4) for the actual metadata display.
"""

import re
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

import db
from ui.components import PrimaryButton, SecondaryButton
from ui.icons import get_icon


def _extract_object_name(text: str) -> str:
    """Extract table name from a query or selection (e.g. 'FROM table_name')."""
    text = text.strip()
    m = re.search(
        r'\bFROM\s+(["`]?[\w]+["`]?\.?["`]?[\w]+["`]?)',
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).replace('"', '').replace('`', '')
    return text.strip('"\' ')


class QuickDescribeDialog(QDialog):
    """Toad Quick Describe (Ctrl+D): input form to launch a full object describe."""

    def __init__(
        self,
        parent=None,
        conn_data: Optional[dict] = None,
        target: str = "",
        worksheet_manager=None,
    ) -> None:
        super().__init__(parent)
        self.conn_data = conn_data or {}
        self.worksheet_manager = worksheet_manager

        self.setWindowTitle("Quick Describe")
        self.setWindowIcon(get_icon("msc.table", color="#2563EB"))
        self.setFixedWidth(470)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.CustomizeWindowHint
        )
        self.setStyleSheet("QDialog { background-color: #FFFFFF; }")

        self._init_ui()
        self._populate_owners()

        if target:
            self.name_edit.setText(_extract_object_name(target))
            self.name_edit.selectAll()
        else:
            self.name_edit.setFocus()

    # ------------------------------------------------------------------
    # UI BUILD
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header Banner ────────────────────────────────────────────
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 12)
        header_layout.setSpacing(12)

        badge = QLabel()
        badge.setFixedSize(38, 38)
        badge.setStyleSheet("""
            QLabel {
                background-color: #EFF6FF;
                border: 1px solid #DBEAFE;
                border-radius: 8px;
            }
        """)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setPixmap(get_icon("msc.table", color="#2563EB").pixmap(20, 20))
        header_layout.addWidget(badge)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title = QLabel("Quick Describe")
        title.setStyleSheet("font-size: 11pt; font-weight: 600; color: #0F172A;")
        sub = QLabel("Fast lookup of database tables, views, and schemas.")
        sub.setStyleSheet("font-size: 8.5pt; color: #64748B;")
        text_col.addWidget(title)
        text_col.addWidget(sub)
        header_layout.addLayout(text_col, 1)
        root.addWidget(header)

        # ── Form Content ─────────────────────────────────────────────
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 4, 20, 18)
        body_layout.setSpacing(12)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # 1. Object Name + Case Sensitivity
        name_row = QHBoxLayout()
        name_row.setSpacing(8)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., employees, hr.departments, v_orders")
        self.name_edit.setFixedHeight(30)
        self.name_edit.setClearButtonEnabled(True)
        self.name_edit.setStyleSheet("""
            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 9pt;
                color: #0F172A;
            }
            QLineEdit:focus {
                border: 1px solid #0078D4;
            }
            QLineEdit::placeholder {
                color: #94A3B8;
            }
        """)
        self.name_edit.returnPressed.connect(self._on_enter_pressed)
        name_row.addWidget(self.name_edit, 1)

        self.case_chk = QCheckBox("Case sensitive")
        self.case_chk.setStyleSheet("font-size: 8.5pt; color: #64748B;")
        name_row.addWidget(self.case_chk)

        name_lbl = QLabel("Object Name:")
        name_lbl.setStyleSheet("font-weight: 600; font-size: 8.5pt; color: #374151;")
        form.addRow(name_lbl, name_row)

        # 2. Owner / Schema Selection
        self.owner_combo = QComboBox()
        self.owner_combo.setFixedHeight(30)
        self.owner_combo.setStyleSheet("""
            QComboBox {
                background: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 8.5pt;
                color: #0F172A;
            }
            QComboBox:hover {
                border-color: #0078D4;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
        """)
        self.owner_combo.setEditable(True)
        owner_lbl = QLabel("Owner / Schema:")
        owner_lbl.setStyleSheet("font-weight: 600; font-size: 8.5pt; color: #374151;")
        form.addRow(owner_lbl, self.owner_combo)

        # 3. Object Type
        type_row = QHBoxLayout()
        type_row.setSpacing(14)

        self.radio_auto = QRadioButton("Auto-detect")
        self.radio_auto.setChecked(True)
        self.radio_auto.setStyleSheet("font-size: 8.5pt; color: #374151;")
        type_row.addWidget(self.radio_auto)

        self.radio_specify = QRadioButton("Specify:")
        self.radio_specify.setStyleSheet("font-size: 8.5pt; color: #374151;")
        type_row.addWidget(self.radio_specify)

        self.type_combo = QComboBox()
        self.type_combo.setFixedHeight(28)
        self.type_combo.setFixedWidth(120)
        self.type_combo.addItems(["Table", "View", "Schema"])
        self.type_combo.setEnabled(False)
        self.type_combo.setStyleSheet("""
            QComboBox {
                background: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 5px;
                padding: 2px 8px;
                font-size: 8.5pt;
                color: #0F172A;
            }
            QComboBox:disabled {
                background: #F1F5F9;
                color: #94A3B8;
            }
            QComboBox::drop-down {
                border: none;
                width: 18px;
            }
        """)
        self.radio_specify.toggled.connect(self.type_combo.setEnabled)
        type_row.addWidget(self.type_combo)
        type_row.addStretch()

        type_lbl = QLabel("Object Type:")
        type_lbl.setStyleSheet("font-weight: 600; font-size: 8.5pt; color: #374151;")
        form.addRow(type_lbl, type_row)

        body_layout.addLayout(form)
        root.addWidget(body)

        # ── Grounded Footer Bar ──────────────────────────────────────
        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border-top: 1px solid #E2E8F0;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 12, 20, 12)
        footer_layout.setSpacing(8)
        footer_layout.addStretch()

        self.close_btn = SecondaryButton("Close")
        self.close_btn.setMinimumWidth(75)
        self.close_btn.setFixedHeight(30)
        self.close_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self.close_btn)

        self.describe_btn = SecondaryButton("Describe")
        self.describe_btn.setIcon(get_icon("msc.inspect", color="#374151"))
        self.describe_btn.setMinimumWidth(95)
        self.describe_btn.setFixedHeight(30)
        self.describe_btn.clicked.connect(self._describe)
        footer_layout.addWidget(self.describe_btn)

        self.desc_close_btn = PrimaryButton("Describe and Close")
        self.desc_close_btn.setMinimumWidth(145)
        self.desc_close_btn.setFixedHeight(30)
        self.desc_close_btn.setDefault(True)
        self.desc_close_btn.clicked.connect(self._describe_and_close)
        footer_layout.addWidget(self.desc_close_btn)

        root.addWidget(footer)

        # Dynamic action button validation
        self.name_edit.textChanged.connect(self._on_text_changed)
        self._on_text_changed(self.name_edit.text())

    def _on_text_changed(self, text: str) -> None:
        has_text = bool(text.strip())
        self.describe_btn.setEnabled(has_text)
        self.desc_close_btn.setEnabled(has_text)

    def _on_enter_pressed(self) -> None:
        if self.name_edit.text().strip():
            self._describe_and_close()

    # ------------------------------------------------------------------
    # DATA
    # ------------------------------------------------------------------
    def _populate_owners(self) -> None:
        self.owner_combo.clear()
        self.owner_combo.addItem("Current / Default Schema")
        if not self.conn_data:
            return
        try:
            conn = db.get_connection(self.conn_data)
            cur = conn.cursor()
            db_type = self.conn_data.get("db_type", "").lower()
            if "postgres" in db_type or "pg" in db_type:
                cur.execute(
                    "SELECT schema_name FROM information_schema.schemata"
                    " WHERE schema_name NOT IN ('pg_catalog','information_schema')"
                    " ORDER BY schema_name"
                )
            elif "oracle" in db_type:
                cur.execute("SELECT username FROM all_users ORDER BY username")
            else:
                cur.execute(
                    "SELECT schema_name FROM information_schema.schemata ORDER BY schema_name"
                )
            for row in cur.fetchall():
                self.owner_combo.addItem(row[0])
            cur.close()
            conn.close()
        except Exception:
            pass

    def _resolve_target(self) -> str:
        name = self.name_edit.text().strip()
        if not name:
            return ""
        owner = self.owner_combo.currentText().strip()
        if owner and owner not in ("Current / Default Schema", "N/A or Unknown", ""):
            return f'"{owner}"."{name}"'
        if self.case_chk.isChecked() and not (name.startswith('"') and name.endswith('"')):
            return f'"{name}"'
        return name

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------
    def _describe(self) -> None:
        t = self._resolve_target()
        if not t:
            self.name_edit.setFocus()
            return
        self._open_describe(t)

    def _describe_and_close(self) -> None:
        t = self._resolve_target()
        if not t:
            self.name_edit.setFocus()
            return
        self.accept()
        self._open_describe(t)

    def _open_describe(self, target: str) -> None:
        from dialogs.tools.object_describe_dialog import ObjectDescribeDialog

        ObjectDescribeDialog(
            parent=self.parent(),
            conn_data=self.conn_data,
            target=target,
        ).show()

    # ------------------------------------------------------------------
    # EVENTS
    # ------------------------------------------------------------------
    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)
