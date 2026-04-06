def display_cell_text(value):
    return "NULL" if value is None else str(value)


def editor_text_from_raw(value):
    return "" if value is None else str(value)


def editor_text_to_db_value(text):
    return None if text == "" else text


def values_equal_for_editor(raw_value, editor_text):
    current_value = editor_text_to_db_value(editor_text)
    if raw_value is None or current_value is None:
        return raw_value is None and current_value is None
    return str(raw_value) == str(current_value)
