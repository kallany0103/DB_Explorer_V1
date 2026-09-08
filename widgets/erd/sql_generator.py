"""SQL forward-engineering: dialect-aware CREATE TABLE script generator and preview dialog."""
import os
import heapq
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QFileDialog, QLabel, QFrame,
    QApplication,
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
import qtawesome as qta

from db.db_connections import get_downloads_dir
from ui.components import PrimaryButton, SecondaryButton, ToastNotification
from widgets.erd.model import DEFAULT_SCHEMA, normalize_entity


class SQLPreviewDialog(QDialog):
    def __init__(self, sql_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SQL Script Preview")
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.resize(840, 640)
        self.setStyleSheet("""
            QDialog {
                background-color: #f6f8fb;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-bottom: 1px solid #e5e9f0;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        header_layout.setSpacing(10)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon("fa5s.code", color="#0078d4").pixmap(18, 18))
        icon_lbl.setStyleSheet("background: transparent; border: none;")

        title_lbl = QLabel("SQL Script Preview")
        title_lbl.setFont(QFont("Segoe UI Variable", 10, QFont.Weight.DemiBold))
        title_lbl.setStyleSheet("color: #1f2937; background: transparent; border: none;")

        header_layout.addWidget(icon_lbl)
        header_layout.addWidget(title_lbl)

        line_count = len(sql_text.strip().splitlines()) if sql_text else 0
        stats_lbl = QLabel(f"{line_count} lines")
        stats_lbl.setFont(QFont("Segoe UI Variable", 8, QFont.Weight.DemiBold))
        stats_lbl.setFixedHeight(22)
        stats_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_lbl.setStyleSheet("""
            QLabel {
                color: #4b5563;
                background-color: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-radius: 11px;
                padding: 0px 10px;
            }
        """)
        header_layout.addWidget(stats_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        header_layout.addStretch()
        root.addWidget(header)

        # ── Code editor ───────────────────────────────────────────────────────
        body = QVBoxLayout()
        body.setContentsMargins(16, 14, 16, 10)
        body.setSpacing(0)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(sql_text)
        self.text_edit.setFont(QFont("Consolas", 10))
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 10px;
                selection-background-color: #45475a;
            }
            QScrollBar:vertical {
                background: #181825;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #45475a;
                border-radius: 4px;
            }
        """)
        body.addWidget(self.text_edit)
        root.addLayout(body)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QFrame()
        footer.setFixedHeight(52)
        footer.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-top: 1px solid #e5e9f0;
            }
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 0, 16, 0)
        footer_layout.setSpacing(8)
        footer_layout.addStretch()

        close_btn = SecondaryButton("Close")
        copy_btn = SecondaryButton(qta.icon("fa5s.copy", color="#374151"), "Copy to Clipboard")
        save_btn = PrimaryButton(qta.icon("fa5s.save", color="#ffffff"), "Save as SQL")

        close_btn.clicked.connect(self.reject)
        copy_btn.clicked.connect(self.copy_sql)
        save_btn.clicked.connect(self.save_sql)

        footer_layout.addWidget(close_btn)
        footer_layout.addWidget(copy_btn)
        footer_layout.addWidget(save_btn)
        root.addWidget(footer)

    def copy_sql(self):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.text_edit.toPlainText())
            ToastNotification.show_toast(self, "SQL script copied to clipboard!", kind="success")

    def save_sql(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save SQL Script", os.path.join(get_downloads_dir(), "schema.sql"), "SQL Files (*.sql)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.text_edit.toPlainText())
                ToastNotification.show_toast(self, "SQL script saved successfully.", kind="success")
            except Exception as e:
                ToastNotification.show_toast(self, f"Failed to save script: {e}", kind="error")


class CheckboxOptionRow(QFrame):
    """An interactive, styled option row with a reliable check-box indicator."""

    def __init__(self, label: str, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                border-radius: 6px;
            }
            QFrame:hover {
                background-color: #f1f5f9;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(10)

        self._icon_lbl = QLabel()
        self._icon_lbl.setFixedSize(18, 18)
        self._icon_lbl.setStyleSheet("background: transparent; border: none;")

        self._text_lbl = QLabel(label)
        self._text_lbl.setFont(QFont("Segoe UI Variable", 9))
        self._text_lbl.setStyleSheet("color: #374151; background: transparent; border: none;")

        layout.addWidget(self._icon_lbl)
        layout.addWidget(self._text_lbl)
        layout.addStretch()

        self._update_icon()

    def _update_icon(self):
        if self._checked:
            self._icon_lbl.setPixmap(qta.icon("fa5s.check-square", color="#0078d4").pixmap(18, 18))
        else:
            self._icon_lbl.setPixmap(qta.icon("fa5.square", color="#9ca3af").pixmap(18, 18))

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self._update_icon()
        super().mousePressEvent(event)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        self._checked = checked
        self._update_icon()


class DialectPickerDialog(QDialog):
    """Styled dialect selection dialog with interactive cards and generation options."""

    DIALECTS = [
        ("postgresql", "fa5s.database",  "#0078d4", "PostgreSQL",       "Full schema with constraints & indexes"),
        ("oracle",     "fa5s.server",    "#ea580c", "Oracle Database",  "PL/SQL compatible tables & identity columns"),
        ("sqlite",     "fa5s.file-alt",  "#16a34a", "SQLite",           "Lightweight file-based schema with autoincrement"),
        ("mysql",      "fa5s.database",  "#0284c7", "MySQL / MariaDB",  "InnoDB tables with foreign keys & auto-increment"),
        ("generic",    "fa5s.code",      "#7c3aed", "Generic SQL",      "Standard ANSI SQL-92 compatible script"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select SQL Dialect")
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self.setFixedWidth(440)
        self.setStyleSheet("QDialog { background-color: #f6f8fb; }")
        self._selected: str = "postgresql"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(54)
        header.setStyleSheet(
            "QFrame { background-color: #ffffff; border-bottom: 1px solid #e5e9f0; }"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(18, 0, 18, 0)
        hl.setSpacing(12)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon("fa5s.file-export", color="#0078d4").pixmap(20, 20))
        icon_lbl.setStyleSheet("background: transparent; border: none;")

        title_lbl = QLabel("Select SQL Dialect")
        title_lbl.setFont(QFont("Segoe UI Variable", 10, QFont.Weight.DemiBold))
        title_lbl.setStyleSheet("color: #1f2937; background: transparent; border: none;")

        subtitle_lbl = QLabel("Choose target database dialect to export")
        subtitle_lbl.setFont(QFont("Segoe UI Variable", 8))
        subtitle_lbl.setStyleSheet("color: #6b7280; background: transparent; border: none;")

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        text_col.addWidget(title_lbl)
        text_col.addWidget(subtitle_lbl)

        hl.addWidget(icon_lbl)
        hl.addLayout(text_col)
        hl.addStretch()
        root.addWidget(header)

        # ── Dialect cards ─────────────────────────────────────────────────────
        body = QVBoxLayout()
        body.setContentsMargins(16, 14, 16, 10)
        body.setSpacing(8)

        self._cards: dict[str, QFrame] = {}
        self._indicators: dict[str, QLabel] = {}
        for key, icon_name, color, label, desc in self.DIALECTS:
            card = self._make_card(key, icon_name, color, label, desc)
            self._cards[key] = card
            body.addWidget(card)

        # ── Options Section ───────────────────────────────────────────────────
        options_title = QLabel("GENERATION OPTIONS")
        options_title.setFont(QFont("Segoe UI Variable", 7, QFont.Weight.Bold))
        options_title.setStyleSheet("color: #9ca3af; letter-spacing: 0.5px; margin-top: 4px; background: transparent;")
        body.addWidget(options_title)

        options_frame = QFrame()
        options_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e5e9f0;
                border-radius: 8px;
            }
        """)
        options_layout = QVBoxLayout(options_frame)
        options_layout.setContentsMargins(6, 6, 6, 6)
        options_layout.setSpacing(2)

        self._drop_cb = CheckboxOptionRow("Include DROP TABLE IF EXISTS statements", checked=False)
        self._fks_cb = CheckboxOptionRow("Include Foreign Key constraints", checked=True)

        options_layout.addWidget(self._drop_cb)
        options_layout.addWidget(self._fks_cb)
        body.addWidget(options_frame)

        root.addLayout(body)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QFrame()
        footer.setFixedHeight(54)
        footer.setStyleSheet(
            "QFrame { background-color: #ffffff; border-top: 1px solid #e5e9f0; }"
        )
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(18, 0, 18, 0)
        fl.setSpacing(8)
        fl.addStretch()

        cancel_btn = SecondaryButton("Cancel")
        ok_btn = PrimaryButton(qta.icon("fa5s.file-code", color="#ffffff"), "Generate SQL")
        ok_btn.setDefault(True)
        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self.accept)

        fl.addWidget(cancel_btn)
        fl.addWidget(ok_btn)
        root.addWidget(footer)

        self._highlight(self._selected)

    def _make_card(self, key: str, icon_name: str, color: str, label: str, desc: str) -> "QFrame":
        card = QFrame()
        card.setObjectName(f"dialect_card_{key}")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setFixedHeight(54)
        card.setStyleSheet(self._card_style(selected=False))

        hl = QHBoxLayout(card)
        hl.setContentsMargins(12, 0, 14, 0)
        hl.setSpacing(12)

        icon_frame = QFrame()
        icon_frame.setFixedSize(32, 32)
        icon_frame.setStyleSheet(f"background: {color}20; border-radius: 7px; border: none;")
        icon_inner = QHBoxLayout(icon_frame)
        icon_inner.setContentsMargins(0, 0, 0, 0)
        lbl_icon = QLabel()
        lbl_icon.setPixmap(qta.icon(icon_name, color=color).pixmap(16, 16))
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_icon.setStyleSheet("background: transparent; border: none;")
        icon_inner.addWidget(lbl_icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        lbl_name = QLabel(label)
        lbl_name.setFont(QFont("Segoe UI Variable", 9, QFont.Weight.DemiBold))
        lbl_name.setStyleSheet("color: #1f2937; background: transparent; border: none;")
        lbl_desc = QLabel(desc)
        lbl_desc.setFont(QFont("Segoe UI Variable", 8))
        lbl_desc.setStyleSheet("color: #6b7280; background: transparent; border: none;")
        text_col.addWidget(lbl_name)
        text_col.addWidget(lbl_desc)

        indicator = QLabel()
        indicator.setFixedSize(18, 18)
        indicator.setStyleSheet("background: transparent; border: none;")
        self._indicators[key] = indicator

        hl.addWidget(icon_frame)
        hl.addLayout(text_col)
        hl.addStretch()
        hl.addWidget(indicator)

        card.mousePressEvent = lambda _e, k=key: self._select(k)
        card.mouseDoubleClickEvent = lambda _e, k=key: (self._select(k), self.accept())
        return card

    def _card_style(self, selected: bool) -> str:
        if selected:
            return (
                "QFrame { background-color: #eff6ff; border: 1.5px solid #0078d4;"
                " border-radius: 8px; }"
            )
        return (
            "QFrame { background-color: #ffffff; border: 1px solid #e5e9f0;"
            " border-radius: 8px; }"
            "QFrame:hover { background-color: #f8fafc; border-color: #cbd5e1; }"
        )

    def _select(self, key: str) -> None:
        self._selected = key
        self._highlight(key)

    def _highlight(self, key: str) -> None:
        for k, card in self._cards.items():
            is_sel = (k == key)
            card.setStyleSheet(self._card_style(selected=is_sel))
            ind = self._indicators.get(k)
            if ind:
                if is_sel:
                    ind.setPixmap(qta.icon("fa5s.check-circle", color="#0078d4").pixmap(18, 18))
                else:
                    ind.setPixmap(qta.icon("fa5s.circle", color="#d1d5db").pixmap(18, 18))

    def selected_dialect(self) -> str:
        return self._selected

    def include_drop(self) -> bool:
        return self._drop_cb.isChecked()

    def include_fks(self) -> bool:
        return self._fks_cb.isChecked()


def _quote_ident(ident: str | None, dialect: str = "generic") -> str:
    """Quote SQL identifiers safely, handling dotted names. Returns empty string for None."""
    if ident is None:
        return ""
    parts = ident.split('.')
    if dialect == "mysql":
        quoted = [p.replace('`', '``') for p in parts]
        return '.'.join(f'`{q}`' for q in quoted)
    quoted = [p.replace('"', '""') for p in parts]
    return '.'.join(f'"{q}"' for q in quoted)


def _quote_default(dval) -> str:
    """Heuristic quoting for default values: leave function/cast forms, quote plain strings."""
    if dval is None:
        return 'NULL'
    if not isinstance(dval, str):
        return str(dval)
    s = dval.strip()
    if s.startswith("'") and s.endswith("'"):
        return s
    if '(' in s or '::' in s:
        return s
    return "'" + s.replace("'", "''") + "'"


def _topological_order(normalized_schema: dict) -> list[str]:
    """Return table names sorted by FK dependency (Kahn's algorithm + min-heap for determinism)."""
    adj = {name: [] for name in normalized_schema.keys()}
    in_degree = {name: 0 for name in normalized_schema.keys()}
    for name, info in normalized_schema.items():
        for fk in info.get('foreign_keys', []):
            target = fk['table']
            if target in in_degree:
                adj.setdefault(target, []).append(name)
                in_degree[name] += 1

    heap = [n for n in normalized_schema.keys() if in_degree[n] == 0]
    heapq.heapify(heap)
    ordered: list[str] = []
    while heap:
        u = heapq.heappop(heap)
        ordered.append(u)
        for v in adj.get(u, []):
            in_degree[v] -= 1
            if in_degree[v] == 0:
                heapq.heappush(heap, v)

    for name in sorted(normalized_schema.keys()):
        if name not in ordered:
            ordered.append(name)

    return ordered


def _build_column_line(col: dict, dialect: str) -> str:
    """Return the SQL column definition line (without trailing comma)."""
    col_name = col['name']
    data_type = col['type'].lower()
    is_pk = col.get('pk')

    if is_pk and "int" in data_type:
        if dialect == "postgresql":
            data_type = "serial"
        elif dialect == "sqlite":
            data_type = "integer"
        elif dialect == "oracle":
            data_type = "NUMBER(*, 0) GENERATED BY DEFAULT AS IDENTITY"
        elif dialect == "mysql":
            data_type = "INT AUTO_INCREMENT"

    if "varchar" in data_type or "varying" in data_type or "text" in data_type:
        if dialect == "oracle":
            data_type = "VARCHAR2(255)" if "text" not in data_type else "CLOB"
        elif "(" not in data_type and "text" not in data_type:
            data_type = "character varying(255)"
        if dialect == "postgresql":
            data_type += ' COLLATE pg_catalog."default"'
    elif "bool" in data_type:
        if dialect == "oracle":
            data_type = "NUMBER(1)"
        elif dialect == "mysql":
            data_type = "TINYINT(1)"
    elif "float" in data_type or "double" in data_type or "real" in data_type:
        if dialect == "oracle":
            data_type = "BINARY_DOUBLE"
    elif "date" in data_type or "time" in data_type:
        if dialect == "oracle":
            data_type = "TIMESTAMP" if ("timestamp" in data_type or "time" in data_type) else "DATE"
        elif dialect == "mysql":
            data_type = "DATETIME" if ("timestamp" in data_type or "time" in data_type) else "DATE"

    col_def = f"    {_quote_ident(col_name, dialect)} {data_type}"

    is_sqlite_inline_pk = (
        dialect == "sqlite"
        and is_pk
        and data_type == "integer"
    )

    if col.get('nullable') is False or (is_pk and not is_sqlite_inline_pk and dialect != "oracle"):
        col_def += " NOT NULL"

    if is_sqlite_inline_pk:
        col_def += " PRIMARY KEY AUTOINCREMENT"

    if 'default' in col and col.get('default') is not None:
        col_def += f" DEFAULT {_quote_default(col['default'])}"

    return col_def


def _build_table_lines(
    full_table_name: str,
    info: dict,
    normalized_schema: dict,
    dialect: str,
    include_drop: bool = False,
    include_fks: bool = True,
) -> list[str]:
    """Return SQL lines for one CREATE TABLE block."""
    schema = (info.get('schema') or DEFAULT_SCHEMA) if dialect == "postgresql" else None
    table_name = info.get('table') or full_table_name.split('.')[-1]
    columns = info['columns']
    pk_cols = [col['name'] for col in columns if col.get('pk')]

    lines = []
    quoted_table = _quote_ident(table_name, dialect)
    quoted_full = f"{_quote_ident(schema, dialect)}.{quoted_table}" if schema else quoted_table

    if include_drop:
        if dialect == "postgresql":
            lines.append(f"DROP TABLE IF EXISTS {quoted_full} CASCADE;\n")
        elif dialect == "oracle":
            lines.append(
                f"BEGIN EXECUTE IMMEDIATE 'DROP TABLE {quoted_table} CASCADE CONSTRAINTS'; "
                "EXCEPTION WHEN OTHERS THEN NULL; END;\n/\n"
            )
        else:
            lines.append(f"DROP TABLE IF EXISTS {quoted_full};\n")

    if dialect == "oracle":
        header = f"CREATE TABLE {quoted_table}"
    elif schema:
        header = f"CREATE TABLE IF NOT EXISTS {quoted_full}"
    else:
        header = f"CREATE TABLE IF NOT EXISTS {quoted_table}"

    col_lines = [_build_column_line(col, dialect) for col in columns]

    sqlite_has_inline_pk = (
        dialect == "sqlite"
        and len(pk_cols) == 1
        and any(
            c['name'] == pk_cols[0] and "int" in c['type'].lower()
            for c in columns
        )
    )
    if pk_cols and not sqlite_has_inline_pk:
        pk_name = f"{table_name}_pkey"
        pk_cols_q = ', '.join(_quote_ident(c, dialect) for c in pk_cols)
        col_lines.append(f"    CONSTRAINT {_quote_ident(pk_name, dialect)} PRIMARY KEY ({pk_cols_q})")

    if include_fks:
        for fk in info.get('foreign_keys', []):
            if not fk.get('from') or not fk.get('to'):
                continue
            fk_name = fk.get('name') or f"fk_{table_name}_{fk['from']}"
            target_info = normalized_schema.get(fk['table'], {})
            target_schema = target_info.get('schema', DEFAULT_SCHEMA) if dialect == "postgresql" else None
            target_table = fk['table'].split('.')[-1]
            target_ref = (
                f"{_quote_ident(target_schema, dialect)}.{_quote_ident(target_table, dialect)}"
                if target_schema else _quote_ident(target_table, dialect)
            )
            clause = (
                f"    CONSTRAINT {_quote_ident(fk_name, dialect)} FOREIGN KEY ({_quote_ident(fk['from'], dialect)}) "
                f"REFERENCES {target_ref}({_quote_ident(fk['to'], dialect)})"
            )
            if fk.get("on_delete"):
                clause += f" ON DELETE {fk['on_delete']}"
            if fk.get("on_update") and dialect != "oracle":
                clause += f" ON UPDATE {fk['on_update']}"
            col_lines.append(clause)

    suffix = " ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;\n" if dialect == "mysql" else " );\n"
    lines.extend([header, "(", ",\n".join(col_lines), suffix])
    return lines


def generate_sql_script(
    schema_data: dict,
    dialect: str = "postgresql",
    include_drop: bool = False,
    include_fks: bool = True,
) -> str:
    """
    Generates an SQL script for the given schema data.
    Returns the SQL script as a string.
    """
    normalized_schema = {}
    for name, info in schema_data.items():
        norm = normalize_entity(info)
        if not norm.get("table"):
            norm["table"] = name.split(".")[-1]
        normalized_schema[name] = norm
    ordered_tables = _topological_order(normalized_schema)

    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    engine_name = {
        "postgresql": "PostgreSQL 12+",
        "oracle": "Oracle Database",
        "sqlite": "SQLite 3",
        "mysql": "MySQL / MariaDB",
        "generic": "Standard ANSI SQL",
    }.get(dialect, dialect.capitalize())

    sql_lines = [
        "-- ===========================================================================",
        "-- ENTERPRISE DATA MODEL EXPORT",
        f"-- Generated on: {gen_time}",
        f"-- Engine: {engine_name}",
        f"-- Tables count: {len(ordered_tables)}",
        "-- ===========================================================================\n",
    ]
    if dialect in ["postgresql", "sqlite"]:
        sql_lines.append("BEGIN TRANSACTION;\n")
    elif dialect == "mysql":
        sql_lines.append("START TRANSACTION;\nSET FOREIGN_KEY_CHECKS = 0;\n")
    elif dialect == "oracle":
        pass
    else:
        sql_lines.append("BEGIN;\n")

    for full_table_name in ordered_tables:
        info = normalized_schema[full_table_name]
        sql_lines.extend(
            _build_table_lines(
                full_table_name,
                info,
                normalized_schema,
                dialect,
                include_drop=include_drop,
                include_fks=include_fks,
            )
        )

    if dialect == "mysql":
        sql_lines.append("SET FOREIGN_KEY_CHECKS = 1;\nCOMMIT;")
    elif dialect != "oracle":
        sql_lines.append("COMMIT;")

    return "\n".join(sql_lines)
