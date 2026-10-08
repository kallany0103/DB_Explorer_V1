"""
dialogs/tools/quick_describe_dialog.py
Toad for Oracle-style Quick Describe (Ctrl+D).

Simple input form: Object Type / Owner / Name -> Describe.
Delegates to ObjectDescribeDialog (F4) for the actual metadata display.
"""

import re
import db
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QCheckBox,
    QPushButton, QRadioButton, QFrame, QButtonGroup,
)

from ui.components import PrimaryButton, SecondaryButton


_FRAME_SS = """
    QFrame#section {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
    }
"""

_COMBO_SS = (
    "QComboBox { background:#ffffff; border:1px solid #cbd5e1; border-radius:4px;"
    " padding:4px 8px; font-size:8.5pt; color:#0f172a; min-height:26px; }"
    "QComboBox:hover { border-color:#0284c7; }"
    "QComboBox::drop-down { border:none; width:20px; }"
    "QComboBox QAbstractItemView { background:#ffffff; border:1px solid #cbd5e1;"
    " selection-background-color:#e0f2fe; selection-color:#0284c7; }"
)

_INPUT_SS = (
    "QLineEdit { background:#ffffff; border:1px solid #cbd5e1; border-radius:4px;"
    " padding:4px 8px; font-size:9pt; color:#0f172a; min-height:26px; }"
    "QLineEdit:focus { border-color:#0284c7; background:#f0f9ff; }"
)

_SECONDARY_BTN_SS = (
    "QPushButton { background:#ffffff; border:1px solid #cbd5e1; border-radius:4px;"
    " padding:5px 14px; font-size:8.5pt; color:#374151; }"
    "QPushButton:hover { background:#f1f5f9; border-color:#94a3b8; }"
    "QPushButton:pressed { background:#e2e8f0; }"
)

_SECTION_LBL_SS = (
    "QLabel { font-weight:700; font-size:8.5pt; color:#475569;"
    " border:none; background:transparent; }"
)


def _extract_object_name(text: str) -> str:
    text = text.strip()
    m = re.search(
        r'\bFROM\s+(["`]?[\w]+["`]?\.?["`]?[\w]+["`]?)',
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).replace('"', '').replace('`', '')
    return text.strip('"\' ')


def _section_frame() -> QFrame:
    f = QFrame()
    f.setObjectName("section")
    f.setStyleSheet(_FRAME_SS)
    return f


def _lbl(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(_SECTION_LBL_SS)
    return l


class QuickDescribeDialog(QDialog):
    """Toad Quick Describe (Ctrl+D): input form to launch a full object describe."""

    def __init__(self, parent=None, conn_data=None,
                 target="", worksheet_manager=None):
        super().__init__(parent)
        self.conn_data = conn_data or {}
        self.worksheet_manager = worksheet_manager

        self.setWindowTitle("Quick Describe")
        self.resize(450, 360)
        self.setMinimumSize(400, 320)
        self.setSizeGripEnabled(True)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
        )

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
    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(10)

        # ── Object Type ──────────────────────────────────────────────
        type_frame = _section_frame()
        type_layout = QVBoxLayout(type_frame)
        type_layout.setContentsMargins(12, 10, 12, 10)
        type_layout.setSpacing(8)
        type_layout.addWidget(_lbl("Object Type"))

        radio_row = QHBoxLayout()
        radio_row.setSpacing(20)
        self.radio_auto = QRadioButton("Let toad figure it out")
        self.radio_auto.setChecked(True)
        self.radio_auto.setStyleSheet("font-size:8.5pt; color:#374151;")
        radio_row.addWidget(self.radio_auto)
        self.radio_specify = QRadioButton("Specify")
        self.radio_specify.setStyleSheet("font-size:8.5pt; color:#374151;")
        radio_row.addWidget(self.radio_specify)
        radio_row.addStretch()
        type_layout.addLayout(radio_row)

        specify_row = QHBoxLayout()
        specify_row.setSpacing(0)
        specify_row.addSpacing(4)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Table", "View", "Schema"])
        self.type_combo.setFixedWidth(160)
        self.type_combo.setStyleSheet(_COMBO_SS)
        self.type_combo.setVisible(False)
        specify_row.addWidget(self.type_combo)
        specify_row.addStretch()
        type_layout.addLayout(specify_row)

        self.radio_auto.toggled.connect(
            lambda on: self.type_combo.setVisible(not on)
        )
        root.addWidget(type_frame)

        # ── Object Owner ─────────────────────────────────────────────
        owner_frame = _section_frame()
        owner_layout = QVBoxLayout(owner_frame)
        owner_layout.setContentsMargins(12, 10, 12, 10)
        owner_layout.setSpacing(6)
        owner_layout.addWidget(_lbl("Object Owner"))
        self.owner_combo = QComboBox()
        self.owner_combo.setEditable(True)
        self.owner_combo.setStyleSheet(_COMBO_SS)
        owner_layout.addWidget(self.owner_combo)
        root.addWidget(owner_frame)

        # ── Object Name ──────────────────────────────────────────────
        name_frame = _section_frame()
        name_layout = QVBoxLayout(name_frame)
        name_layout.setContentsMargins(12, 10, 12, 10)
        name_layout.setSpacing(6)
        name_layout.addWidget(_lbl("Object Name"))

        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g.  employees")
        self.name_edit.setStyleSheet(_INPUT_SS)
        self.name_edit.returnPressed.connect(self._describe)
        name_row.addWidget(self.name_edit, stretch=1)
        self.case_chk = QCheckBox("Case sensitive")
        self.case_chk.setStyleSheet("font-size:8pt; color:#6b7280;")
        name_row.addWidget(self.case_chk)
        name_layout.addLayout(name_row)
        root.addWidget(name_frame)

        root.addStretch(1)

        # ── Separator ────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("QFrame { color:#e2e8f0; }")
        root.addWidget(sep)

        # ── Buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self.describe_btn = PrimaryButton("Describe")
        self.describe_btn.setMinimumWidth(90)
        self.describe_btn.clicked.connect(self._describe)
        btn_row.addWidget(self.describe_btn)

        self.desc_close_btn = QPushButton("Describe and Close")
        self.desc_close_btn.setMinimumWidth(132)
        self.desc_close_btn.setStyleSheet(_SECONDARY_BTN_SS)
        self.desc_close_btn.clicked.connect(self._describe_and_close)
        btn_row.addWidget(self.desc_close_btn)

        self.close_btn = SecondaryButton("Close")
        self.close_btn.setMinimumWidth(70)
        self.close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.close_btn)

        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # DATA
    # ------------------------------------------------------------------
    def _populate_owners(self):
        self.owner_combo.clear()
        self.owner_combo.addItem("N/A or Unknown")
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
        if owner and owner not in ("N/A or Unknown", ""):
            return f'"{owner}"."{name}"' 
        return name

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------
    def _describe(self):
        t = self._resolve_target()
        if not t:
            self.name_edit.setFocus()
            return
        self._open_describe(t)

    def _describe_and_close(self):
        t = self._resolve_target()
        if not t:
            self.name_edit.setFocus()
            return
        self.accept()
        self._open_describe(t)

    def _open_describe(self, target: str):
        from dialogs.tools.object_describe_dialog import ObjectDescribeDialog
        ObjectDescribeDialog(
            parent=self.parent(),
            conn_data=self.conn_data,
            target=target,
        ).show()

    # ------------------------------------------------------------------
    # EVENTS
    # ------------------------------------------------------------------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)
