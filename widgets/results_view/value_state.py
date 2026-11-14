def get_grid_null_text(manager) -> str:
    main_win = getattr(manager, "main_window", None)
    val = getattr(main_win, "grid_null_text", "NULL")
    return "NULL" if val is None else str(val)


def display_cell_text(value, null_text: str = "NULL"):
    if value is None:
        return null_text
    text = str(value)
    if "\n" in text or "\r" in text:
        return " ".join(text.split())
    return text


def editor_text_from_raw(value):
    return "" if value is None else str(value)


def editor_text_to_db_value(text):
    return None if text == "" else text


def values_equal_for_editor(raw_value, editor_text):
    current_value = editor_text_to_db_value(editor_text)
    if raw_value is None or current_value is None:
        return raw_value is None and current_value is None
    return str(raw_value) == str(current_value)
