import re
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


def apply_select_pagination(query, current_tab, preserve_pagination=False):
    if not query:
        return query

    normalized_query = query.strip().rstrip(";")
    upper_query = normalized_query.upper()

    if upper_query.startswith("SELECT") and not preserve_pagination and "OFFSET" not in upper_query:
        current_tab.current_offset = 0
        current_tab.current_page = 1

    limit = getattr(current_tab, "current_limit", 0)
    offset = getattr(current_tab, "current_offset", 0)

    if upper_query.startswith("SELECT") and limit > 0:
        if "LIMIT" not in upper_query:
            normalized_query += f" LIMIT {limit}"
            upper_query = normalized_query.upper()
        if offset > 0 and "OFFSET" not in upper_query:
            normalized_query += f" OFFSET {offset}"

    return normalized_query + ";"


def resolve_output_tab_index(manager, current_tab, output_mode="current"):
    output_tab_index = None
    if output_mode == "new":
        output_tab_index = manager.results_manager.create_output_tab(current_tab, activate=True)
    else:
        output_tabs = current_tab.findChild(QTabWidget, "output_tabs")
        if output_tabs and output_tabs.currentIndex() >= 0:
            output_tab_index = output_tabs.currentIndex()
    return output_tab_index
