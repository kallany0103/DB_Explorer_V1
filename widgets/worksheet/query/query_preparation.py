import re
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QComboBox, QPlainTextEdit, QTabWidget

from widgets.worksheet.code_editor import CodeEditor

IDENT_SEG_PAT = r'(?:"[^"]+"|\`[^\`]+\`|\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_#$]*)'
IDENT_FIND_PAT = re.compile(rf'{IDENT_SEG_PAT}(?:\s*\.\s*{IDENT_SEG_PAT})*')

DOLLAR_TAG_PATTERN = re.compile(r"^\$[A-Za-z0-9_]*\$")
PLSQL_BLOCK_START_KEYWORDS = {"BEGIN", "DECLARE"}
PLSQL_DDL_PATTERN = re.compile(
    r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:NON)?EDITIONABLE\s+)?(PROCEDURE|FUNCTION|PACKAGE(?:\s+BODY)?|TRIGGER|TYPE(?:\s+BODY)?)\b",
    re.IGNORECASE,
)


def split_sql_statements(text: str) -> list[tuple[int, int, str]]:
    """Split text into individual SQL / PL-SQL statements preserving statement bounds.

    Returns a list of (start_offset, end_offset, stripped_sql).
    """
    if not text:
        return []

    statements: list[tuple[int, int, str]] = []
    length = len(text)
    idx = 0
    stmt_start = 0
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False
    dollar_tag: str | None = None
    had_dollar_quote = False

    current_tokens: list[str] = []
    current_word: list[str] = []
    in_plsql = False
    block_depth = 0

    while idx < length:
        ch = text[idx]
        nxt = text[idx + 1] if idx + 1 < length else ""

        # 1. Line comment
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            idx += 1
            continue

        # 2. Block comment
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                idx += 2
                continue
            idx += 1
            continue

        # 3. PostgreSQL dollar quote ($$ or $tag$)
        if dollar_tag is not None:
            if text.startswith(dollar_tag, idx):
                idx += len(dollar_tag)
                dollar_tag = None
                in_plsql = False
                block_depth = 0
                continue
            idx += 1
            continue

        # 4. Single quote
        if in_single_quote:
            if ch == "'":
                if nxt == "'":
                    idx += 2
                    continue
                in_single_quote = False
            idx += 1
            continue

        # 5. Double quote
        if in_double_quote:
            if ch == '"':
                in_double_quote = False
            idx += 1
            continue

        # Start of comments
        if ch == "-" and nxt == "-":
            in_line_comment = True
            idx += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            idx += 2
            continue

        # PostgreSQL dollar quote start
        if ch == "$":
            m = DOLLAR_TAG_PATTERN.match(text[idx:])
            if m:
                dollar_tag = m.group(0)
                idx += len(dollar_tag)
                had_dollar_quote = True
                continue

        # Start of quotes
        if ch == "'":
            in_single_quote = True
            idx += 1
            continue
        if ch == '"':
            in_double_quote = True
            idx += 1
            continue

        # Slash on a line by itself (Oracle block terminator, allowing leading/trailing whitespace)
        if ch == "/":
            p = idx - 1
            while p >= 0 and text[p] in " \t\r":
                p -= 1
            if p < 0 or text[p] == "\n":
                j = idx + 1
                while j < length and text[j] in " \t\r":
                    j += 1
                if j >= length or text[j] == "\n":
                    stmt_text = text[stmt_start:idx].strip()
                    if stmt_text:
                        statements.append((stmt_start, idx, stmt_text))
                    idx = j + 1
                    stmt_start = idx
                    in_plsql = False
                    had_dollar_quote = False
                block_depth = 0
                current_tokens = []
                current_word = []
                continue

        # Token tracking outside quotes/comments
        if ch.isalnum() or ch in ("_", "$", "#"):
            current_word.append(ch)
        else:
            if current_word:
                w = "".join(current_word).upper()
                current_word = []
                current_tokens.append(w)

                if not in_plsql and not had_dollar_quote:
                    fw = current_tokens[0]
                    if fw in PLSQL_BLOCK_START_KEYWORDS:
                        in_plsql = True
                        block_depth = 1
                    elif fw == "CREATE":
                        joined = " ".join(current_tokens[:6])
                        if PLSQL_DDL_PATTERN.match(joined):
                            in_plsql = True
                            block_depth = 1
                elif in_plsql:
                    if w in ("BEGIN", "CASE", "LOOP", "IF"):
                        block_depth += 1
                if in_plsql and len(current_tokens) >= 2 and current_tokens[-2] == "END":
                    block_depth = max(0, block_depth - 1)

            if ch == ";":
                if in_plsql and current_tokens and current_tokens[-1] == "END":
                    block_depth = max(0, block_depth - 1)

                if (not in_plsql and not had_dollar_quote) or (had_dollar_quote and dollar_tag is None) or block_depth == 0:
                    stmt_text = text[stmt_start:idx].strip()
                    if stmt_text:
                        statements.append((stmt_start, idx, stmt_text))
                    stmt_start = idx + 1
                    in_plsql = False
                    had_dollar_quote = False
                    block_depth = 0
                    current_tokens = []

        idx += 1

    if stmt_start < length:
        stmt_text = text[stmt_start:].strip()
        if stmt_text:
            statements.append((stmt_start, length, stmt_text))

    return statements


def get_query_editor(current_tab):
    query_editor = current_tab.findChild(CodeEditor, "query_editor")
    if not query_editor:
        query_editor = current_tab.findChild(QPlainTextEdit, "query_editor")
    return query_editor


def extract_query_under_cursor(query_editor):
    cursor = query_editor.textCursor()

    # If there's a selection, execute the selection
    if cursor.hasSelection():
        return cursor.selectedText().replace("\u2029", "\n").strip()

    cursor_pos = cursor.position()
    full_text = query_editor.toPlainText()
    if not full_text.strip():
        return ""

    statements = split_sql_statements(full_text)
    if not statements:
        return full_text.strip()

    for start, end, stmt_text in statements:
        if start <= cursor_pos <= end:
            return stmt_text

    # If cursor is between statements or in whitespace, return closest statement
    closest = min(statements, key=lambda s: min(abs(s[0] - cursor_pos), abs(s[1] - cursor_pos)))
    return closest[2]


def extract_identifier_under_cursor(query_editor) -> str:
    """Extracts a table or object identifier directly under the editor text cursor."""
    if not query_editor:
        return ""
    cursor = query_editor.textCursor()
    if cursor.hasSelection():
        return cursor.selectedText().replace('\u2029', '\n').strip()

    block = cursor.block()
    line_text = block.text()
    col = cursor.positionInBlock()

    for m in IDENT_FIND_PAT.finditer(line_text):
        if m.start() <= col <= m.end():
            return m.group(0).strip()
    return ""


def get_tab_connection_data(current_tab):
    db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
    if not db_combo_box:
        return None
    index = db_combo_box.currentIndex()
    return db_combo_box.itemData(index)


def resolve_query_context(current_tab, conn_data=None, query=None):
    resolved_conn_data = conn_data if isinstance(conn_data, dict) else None
    resolved_query = query if isinstance(query, str) else None

    if resolved_conn_data is not None and resolved_query is not None:
        return resolved_conn_data, resolved_query

    query_editor = get_query_editor(current_tab)
    if resolved_query is None and query_editor:
        resolved_query = extract_query_under_cursor(query_editor)

    if resolved_conn_data is None:
        resolved_conn_data = get_tab_connection_data(current_tab)

    return resolved_conn_data, resolved_query


def _strip_leading_sql_comments(sql: str) -> str:
    """Return SQL with leading whitespace, -- comments, and /* */ comments skipped."""
    pos = 0
    length = len(sql)
    while pos < length:
        if sql[pos].isspace():
            pos += 1
        elif sql.startswith("--", pos):
            nl = sql.find("\n", pos)
            pos = length if nl == -1 else nl + 1
        elif sql.startswith("/*", pos):
            end = sql.find("*/", pos + 2)
            pos = length if end == -1 else end + 2
        else:
            break
    return sql[pos:]


def _strip_sql_literals_and_comments(sql: str) -> str:
    """Replace SQL comments and quoted literals/identifiers with spaces for clause checks."""
    return re.sub(
        r"--[^\n]*|/\*[\s\S]*?\*/|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"",
        " ",
        sql,
    )


def is_oracle_connection(conn_data_or_tab) -> bool:
    """Check if the provided connection data or tab corresponds to an Oracle database."""
    if not conn_data_or_tab:
        return False
    if isinstance(conn_data_or_tab, dict):
        code = str(conn_data_or_tab.get("code") or conn_data_or_tab.get("db_type") or "").upper()
        return code in ("ORACLE", "ORACLE_DB", "ORACLE_FA")
    conn_data = getattr(conn_data_or_tab, "_conn_data", None)
    if not conn_data and hasattr(conn_data_or_tab, "findChild"):
        combo = conn_data_or_tab.findChild(QComboBox, "db_combo_box")
        if combo:
            conn_data = combo.currentData()
    if isinstance(conn_data, dict):
        code = str(conn_data.get("code") or conn_data.get("db_type") or "").upper()
        return code in ("ORACLE", "ORACLE_DB", "ORACLE_FA")
    return False


def apply_select_pagination(query: str, current_tab, preserve_pagination: bool = False) -> str:
    if not query:
        return query

    raw = query.strip()
    had_trailing_semicolon = raw.endswith(";")
    normalized_query = raw.rstrip(";")
    leading_sql = _strip_leading_sql_comments(normalized_query)
    is_select_like = bool(re.match(r"^\(?\s*(?:SELECT|WITH)\b", leading_sql, re.IGNORECASE))
    token_sql = _strip_sql_literals_and_comments(normalized_query)

    if is_select_like and not preserve_pagination and not re.search(r"\bOFFSET\b", token_sql, re.IGNORECASE):
        if current_tab:
            current_tab.current_offset = 0
            current_tab.current_page = 1

    limit = getattr(current_tab, "current_limit", 0) if current_tab else 0
    offset = getattr(current_tab, "current_offset", 0) if current_tab else 0
    is_oracle = is_oracle_connection(current_tab)

    if is_select_like:
        has_limit = bool(re.search(r"\bLIMIT\b|\bFETCH\s+(?:FIRST|NEXT)\b", token_sql, re.IGNORECASE))
        has_offset = bool(re.search(r"\bOFFSET\b", token_sql, re.IGNORECASE))
        if limit > 0 and not has_limit:
            if is_oracle:
                if offset > 0 and not has_offset:
                    normalized_query += f" OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"
                else:
                    normalized_query += f" FETCH FIRST {limit} ROWS ONLY"
            else:
                normalized_query += f" LIMIT {limit}"
                if offset > 0 and not has_offset:
                    normalized_query += f" OFFSET {offset}"
        elif offset > 0 and not has_offset:
            if is_oracle:
                normalized_query += f" OFFSET {offset} ROWS"
            else:
                normalized_query += f" OFFSET {offset}"
        return normalized_query + ";"

    if had_trailing_semicolon and not raw.endswith("/;"):
        return normalized_query + ";"
    return normalized_query


_TRAILING_PAGINATION_RE = re.compile(
    r"(\s+)(?:LIMIT\s+\d+(?:\s+OFFSET\s+\d+)?|(?:OFFSET\s+\d+\s+ROWS?\s+)?FETCH\s+(?:FIRST|NEXT)\s+\d+\s+ROWS?\s+ONLY)\s*$",
    re.IGNORECASE,
)


def apply_limit_to_sql_statement(
    sql: str,
    limit: int,
    overwrite_existing: bool = True,
    is_oracle: bool = False,
) -> str:
    """Insert, update, or remove a trailing LIMIT / FETCH FIRST clause in a SELECT/WITH statement."""
    if not sql or not sql.strip():
        return sql

    rstripped = sql.rstrip()
    trailing_ws = sql[len(rstripped):]
    had_semi = rstripped.endswith(";")
    body = rstripped[:-1].rstrip() if had_semi else rstripped

    leading_sql = _strip_leading_sql_comments(body)
    if not re.match(r"^\(?\s*(?:SELECT|WITH)\b", leading_sql, re.IGNORECASE):
        return sql

    match = _TRAILING_PAGINATION_RE.search(body)
    clause = f"FETCH FIRST {limit} ROWS ONLY" if is_oracle else f"LIMIT {limit}"

    if limit > 0:
        if match:
            if not overwrite_existing:
                return sql
            sep = match.group(1)
            new_body = f"{body[:match.start()]}{sep}{clause}"
        else:
            sep = "\n" if "\n" in body else " "
            new_body = f"{body}{sep}{clause}"
    else:
        if not (match and overwrite_existing):
            return sql
        new_body = body[:match.start()].rstrip()

    semi_str = ";" if had_semi else ""
    return f"{new_body}{semi_str}{trailing_ws}"


def sync_editor_limit(
    editor,
    limit: int,
    overwrite_existing: bool = True,
    is_oracle: bool = False,
) -> bool:
    """Update the active SQL statement in the editor to reflect the selected row limit."""
    if editor is None:
        return False
    text = editor.toPlainText()
    if not text.strip():
        return False

    statements = split_sql_statements(text)
    if not statements:
        return False

    cursor_pos = editor.textCursor().position()
    target = statements[-1]
    for start, end, stmt in statements:
        if start <= cursor_pos <= end + 1:
            target = (start, end, stmt)
            break

    start, end, _stmt = target
    raw_slice = text[start:end]
    # Include trailing semicolon if right after statement end
    slice_end = end + 1 if end < len(text) and text[end] == ";" else end
    raw_slice = text[start:slice_end]
    updated = apply_limit_to_sql_statement(
        raw_slice, limit, overwrite_existing=overwrite_existing, is_oracle=is_oracle
    )
    if updated == raw_slice:
        return False

    edit_cursor = QTextCursor(editor.document())
    edit_cursor.beginEditBlock()
    edit_cursor.setPosition(start)
    edit_cursor.setPosition(slice_end, QTextCursor.MoveMode.KeepAnchor)
    edit_cursor.insertText(updated)
    edit_cursor.endEditBlock()
    return True


def resolve_output_tab_index(manager, current_tab, output_mode="current"):
    output_tab_index = None
    if output_mode == "new":
        output_tab_index = manager.results_manager.create_output_tab(current_tab, activate=True)
    else:
        output_tabs = current_tab.findChild(QTabWidget, "output_tabs")
        if output_tabs and output_tabs.currentIndex() >= 0:
            output_tab_index = output_tabs.currentIndex()
    return output_tab_index
