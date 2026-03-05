# signals.py
from PyQt6.QtCore import QObject, pyqtSignal

class ProcessSignals(QObject):
    started = pyqtSignal(str, dict)
    finished = pyqtSignal(str, str, float, int)
    error = pyqtSignal(str, str)
      
class QuerySignals(QObject):
    finished = pyqtSignal(dict, str, list, list, int, float, bool)  
    # conn_data, query, results, columns, row_count, elapsed_time, is_select_query

    error = pyqtSignal(dict, str, int, float, str)  
    # conn_data, query, row_count, elapsed_time, error_message

class MetadataSignals(QObject):
    finished = pyqtSignal(dict, list, str)
    # metadata_dict, original_columns, table_name
    
    error = pyqtSignal(str)
    # error_message


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return list(value) if isinstance(value, tuple) else [value]


def _as_str(value):
    return "" if value is None else str(value)


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_bool(value):
    return bool(value)


def emit_process_started(signals, process_id, data):
    normalized_data = _as_dict(data)
    normalized_process_id = _as_str(process_id or normalized_data.get("pid"))
    payload = dict(normalized_data)
    payload["pid"] = normalized_process_id
    signals.started.emit(normalized_process_id, payload)


def emit_process_finished(signals, process_id, message, time_taken, row_count):
    signals.finished.emit(
        _as_str(process_id),
        _as_str(message),
        _as_float(time_taken),
        _as_int(row_count),
    )


def emit_process_error(signals, process_id, error_message):
    signals.error.emit(_as_str(process_id), _as_str(error_message))


def emit_query_finished(signals, conn_data, query, results, columns, row_count, elapsed_time, is_select_query):
    signals.finished.emit(
        _as_dict(conn_data),
        _as_str(query),
        _as_list(results),
        _as_list(columns),
        _as_int(row_count),
        _as_float(elapsed_time),
        _as_bool(is_select_query),
    )


def emit_query_error(signals, conn_data, query, row_count, elapsed_time, error_message):
    signals.error.emit(
        _as_dict(conn_data),
        _as_str(query),
        _as_int(row_count),
        _as_float(elapsed_time),
        _as_str(error_message),
    )


def emit_metadata_finished(signals, metadata_dict, original_columns, table_name):
    signals.finished.emit(_as_dict(metadata_dict), _as_list(original_columns), _as_str(table_name))


def emit_metadata_error(signals, error_message):
    signals.error.emit(_as_str(error_message))
