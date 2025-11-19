# signals.py
from PyQt6.QtCore import QObject, pyqtSignal

class ProcessSignals(QObject):
    started = pyqtSignal(str, dict)
    finished = pyqtSignal(str, str, float)
    error = pyqtSignal(str, str)
      
class QuerySignals(QObject):
    finished = pyqtSignal(dict, str, list, list, int, float, bool)  
    # conn_data, query, results, columns, row_count, elapsed_time, is_select_query

    error = pyqtSignal(dict, str, int, float, str)  
    # conn_data, query, row_count, elapsed_time, error_message
