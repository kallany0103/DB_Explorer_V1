"""SQL forward-engineering: dialect-aware CREATE TABLE script generator and preview dialog."""
import heapq
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QFileDialog, QMessageBox
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from widgets.erd.model import DEFAULT_SCHEMA, normalize_entity


class SQLPreviewDialog(QDialog):
    def __init__(self, sql_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SQL Script")
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(sql_text)
        self.text_edit.setFont(QFont("Consolas", 10))
        layout.addWidget(self.text_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close)
        buttons.accepted.connect(self.save_sql)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save_sql(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save SQL Script", "schema.sql", "SQL Files (*.sql)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.text_edit.toPlainText())
                QMessageBox.information(self, "Success", "SQL script saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save script: {str(e)}")


def _quote_ident(ident: str) -> str:
    """Quote SQL identifiers safely, handling dotted names."""
    parts = ident.split('.')
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

    if "varchar" in data_type or "varying" in data_type or "text" in data_type:
        if "(" not in data_type and "text" not in data_type:
            data_type = "character varying(255)"
        if dialect == "postgresql":
            data_type += ' COLLATE pg_catalog."default"'

    col_def = f"    {_quote_ident(col_name)} {data_type}"

    is_sqlite_inline_pk = (
        dialect == "sqlite"
        and is_pk
        and data_type == "integer"
    )

    if col.get('nullable') is False or (is_pk and not is_sqlite_inline_pk):
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
) -> list[str]:
    """Return SQL lines for one CREATE TABLE block."""
    schema = info.get('schema', DEFAULT_SCHEMA) if dialect == "postgresql" else None
    table_name = info.get('table', full_table_name.split('.')[-1])
    columns = info['columns']
    pk_cols = [col['name'] for col in columns if col.get('pk')]

    if schema:
        header = f"CREATE TABLE IF NOT EXISTS {_quote_ident(schema)}.{_quote_ident(table_name)}"
    else:
        header = f"CREATE TABLE IF NOT EXISTS {_quote_ident(table_name)}"

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
        pk_cols_q = ', '.join(_quote_ident(c) for c in pk_cols)
        col_lines.append(f"    CONSTRAINT {_quote_ident(pk_name)} PRIMARY KEY ({pk_cols_q})")

    for fk in info.get('foreign_keys', []):
        fk_name = fk.get('name', f"fk_{table_name}_{fk['from']}")
        target_info = normalized_schema.get(fk['table'], {})
        target_schema = target_info.get('schema', DEFAULT_SCHEMA) if dialect == "postgresql" else None
        target_table = fk['table'].split('.')[-1]
        target_ref = (
            f"{_quote_ident(target_schema)}.{_quote_ident(target_table)}"
            if target_schema else _quote_ident(target_table)
        )
        clause = (
            f"    CONSTRAINT {_quote_ident(fk_name)} FOREIGN KEY ({_quote_ident(fk['from'])}) "
            f"REFERENCES {target_ref}({_quote_ident(fk['to'])})"
        )
        if fk.get("on_delete"):
            clause += f" ON DELETE {fk['on_delete']}"
        if fk.get("on_update"):
            clause += f" ON UPDATE {fk['on_update']}"
        col_lines.append(clause)

    return [header, "(", ",\n".join(col_lines), " );\n"]


def generate_sql_script(schema_data: dict, dialect: str = "postgresql") -> str:
    """
    Generates an SQL script for the given schema data.
    Returns the SQL script as a string.
    """
    normalized_schema = {name: normalize_entity(info) for name, info in schema_data.items()}
    ordered_tables = _topological_order(normalized_schema)

    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sql_lines = [
        "-- ===========================================================================",
        "-- ENTERPRISE DATA MODEL EXPORT",
        f"-- Generated on: {gen_time}",
        f"-- Engine: {dialect.capitalize()} / Standard SQL Compatibility",
        "-- Description: ",
        "-- ===========================================================================\n",
    ]
    if dialect in ["postgresql", "sqlite"]:
        sql_lines.append("BEGIN TRANSACTION;\n")
    else:
        sql_lines.append("BEGIN;\n")

    for full_table_name in ordered_tables:
        info = normalized_schema[full_table_name]
        sql_lines.extend(_build_table_lines(full_table_name, info, normalized_schema, dialect))

    sql_lines.append("COMMIT;")
    return "\n".join(sql_lines)
