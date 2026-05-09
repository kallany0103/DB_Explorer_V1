# signals.py
#from PyQt6.QtCore import QObject, pyqtSignal

from PySide6.QtCore import QObject, Signal

class ProcessSignals(QObject):
    started = Signal(object, object)
    finished = Signal(object, object, object, object)
    error = Signal(object, object)
      
class QuerySignals(QObject):
    finished = Signal(object, object, object, object, object, object, object, object)
    # conn_data, query, results, columns, column_specs, row_count, elapsed_time, is_select_query

    error = Signal(object, object, object, object, object)  
    # conn_data, query, row_count, elapsed_time, error_message


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


class AppTransactionTracker:
    """Tracks worksheet-initiated transactions and tuple activity to filter out database noise."""
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppTransactionTracker, cls).__new__(cls)
            cls._instance.commits = 0
            cls._instance.rollbacks = 0
            cls._instance.tup_ins = 0
            cls._instance.tup_upd = 0
            cls._instance.tup_del = 0
            cls._instance.tup_fet = 0
            cls._instance.tup_ret = 0
            cls._instance.exec_time = 0.0
        return cls._instance

    def add_commit(self): self.commits += 1
    def add_rollback(self): self.rollbacks += 1
    def add_tuples(self, ins=0, upd=0, delt=0, fet=0, ret=0):
        self.tup_ins += ins
        self.tup_upd += upd
        self.tup_del += delt
        self.tup_fet += fet
        self.tup_ret += ret
    
    def add_exec_time(self, ms):
        self.exec_time += float(ms)

    def get_stats(self):
        return {
            "commits": self.commits,
            "rollbacks": self.rollbacks,
            "tup_ins": self.tup_ins,
            "tup_upd": self.tup_upd,
            "tup_del": self.tup_del,
            "tup_fet": self.tup_fet,
            "tup_ret": self.tup_ret,
            "exec_time": self.exec_time
        }


tracker = AppTransactionTracker()


def emit_process_started(signals, process_id, data):

    normalized_data = _as_dict(data)
    normalized_process_id = _as_str(process_id or normalized_data.get("pid"))
    payload = dict(normalized_data)
    payload["pid"] = normalized_process_id
    try:
        signals.started.emit(normalized_process_id, payload)
    except RuntimeError:
        pass


def emit_process_finished(signals, process_id, message, time_taken, row_count):
    try:
        signals.finished.emit(
            _as_str(process_id),
            _as_str(message),
            _as_float(time_taken),
            _as_int(row_count),
        )
    except RuntimeError:
        pass


def emit_process_error(signals, process_id, error_message):
    try:
        signals.error.emit(_as_str(process_id), _as_str(error_message))
    except RuntimeError:
        pass


def emit_query_finished(signals, conn_data, query, results, columns, column_specs, row_count, elapsed_time, is_select_query):
    # Track explicit or implicit commits for worksheet activity
    q_upper = str(query).upper().strip()
    
    # 1. Transactions
    if "ROLLBACK" in q_upper:
        tracker.add_rollback()
    elif "COMMIT" in q_upper or not is_select_query:
        tracker.add_commit()

    # 2. Tuples
    rc = int(row_count or 0)
    if q_upper.startswith("INSERT"):
        tracker.add_tuples(ins=rc)
    elif q_upper.startswith("UPDATE"):
        tracker.add_tuples(upd=rc)
    elif q_upper.startswith("DELETE"):
        tracker.add_tuples(delt=rc)
    elif is_select_query:
        # Returned = total rows matched, Fetched = total rows sent to UI
        tracker.add_tuples(ret=rc, fet=rc)
    
    # 3. Execution Time
    tracker.add_exec_time(elapsed_time)

    try:



        signals.finished.emit(
            _as_dict(conn_data),
            _as_str(query),
            _as_list(results),
            _as_list(columns),
            _as_list(column_specs),
            _as_int(row_count),
            _as_float(elapsed_time),
            _as_bool(is_select_query),
        )
    except RuntimeError:
        pass


def emit_query_error(signals, conn_data, query, row_count, elapsed_time, error_message):
    # Track rollbacks for worksheet activity errors
    tracker.add_rollback()
    
    # Track execution time even for errors
    tracker.add_exec_time(elapsed_time)

    try:

        signals.error.emit(
            _as_dict(conn_data),
            _as_str(query),
            _as_int(row_count),
            _as_float(elapsed_time),
            _as_str(error_message),
        )
    except RuntimeError:
        pass


