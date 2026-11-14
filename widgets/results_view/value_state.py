import datetime


def get_grid_null_text(manager) -> str:
    main_win = getattr(manager, "main_window", None)
    val = getattr(main_win, "grid_null_text", "NULL")
    return "NULL" if val is None else str(val)


def get_grid_datetime_format(manager) -> str:
    main_win = getattr(manager, "main_window", None)
    val = getattr(main_win, "grid_datetime_format", "YYYY-MM-DD HH:mm:ss")
    return "YYYY-MM-DD HH:mm:ss" if not val else str(val)


def format_datetime_value(value, dt_format: str = "YYYY-MM-DD HH:mm:ss") -> str:
    """Format date/datetime objects or strings according to user preferences."""
    if value is None:
        return ""
    if not isinstance(value, (datetime.datetime, datetime.date)):
        return str(value)

    is_dt = isinstance(value, datetime.datetime)
    if dt_format == "ISO-8601 (YYYY-MM-DDTHH:mm:ss)":
        return value.strftime("%Y-%m-%dT%H:%M:%S") if is_dt else value.strftime("%Y-%m-%d")
    elif dt_format == "MM/DD/YYYY HH:mm:ss":
        return value.strftime("%m/%d/%Y %H:%M:%S") if is_dt else value.strftime("%m/%d/%Y")
    elif dt_format == "DD/MM/YYYY HH:mm:ss":
        return value.strftime("%d/%m/%Y %H:%M:%S") if is_dt else value.strftime("%d/%m/%Y")
    elif dt_format == "Locale Default":
        return value.strftime("%x %X") if is_dt else value.strftime("%x")
    else:  # "YYYY-MM-DD HH:mm:ss"
        return value.strftime("%Y-%m-%d %H:%M:%S") if is_dt else value.strftime("%Y-%m-%d")


def display_cell_text(value, null_text: str = "NULL", dt_format: str | None = None):
    if value is None:
        return null_text
    if isinstance(value, (datetime.datetime, datetime.date)):
        fmt = dt_format or "YYYY-MM-DD HH:mm:ss"
        return format_datetime_value(value, fmt)
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
