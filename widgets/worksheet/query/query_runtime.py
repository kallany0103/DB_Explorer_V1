import time
import uuid
from functools import partial

from PyQt6.QtCore import QTimer


def begin_query_runtime(manager, current_tab, tab_status_label, runnable):
    operation_id = uuid.uuid4().hex
    progress_timer = QTimer(manager)
    timeout_timer = QTimer(manager)
    timeout_timer.setSingleShot(True)

    manager.tab_timers[current_tab] = {
        "timer": progress_timer,
        "start_time": time.time(),
        "timeout_timer": timeout_timer,
        "operation_id": operation_id,
    }

    signals = getattr(runnable, "signals", None)
    if signals is not None:
        signals._operation_id = operation_id
        signals._runnable_ref = runnable

    progress_timer.timeout.connect(partial(manager.update_timer_label, tab_status_label, current_tab))
    progress_timer.start(100)

    timeout_timer.timeout.connect(partial(manager.handle_query_timeout, current_tab, runnable))

    manager.running_queries[current_tab] = runnable
    manager.cancel_action.setEnabled(True)
    manager.thread_pool.start(runnable)
    timeout_timer.start(manager.QUERY_TIMEOUT)
    return operation_id


def clear_query_timers(manager, tab, stop_timeout=True):
    timer_state = manager.tab_timers.get(tab)
    if not timer_state:
        return

    timer = timer_state.get("timer")
    if timer:
        timer.stop()

    if stop_timeout:
        timeout_timer = timer_state.get("timeout_timer")
        if timeout_timer:
            timeout_timer.stop()

    del manager.tab_timers[tab]


def clear_running_query(manager, tab):
    if tab in manager.running_queries:
        del manager.running_queries[tab]
    if not manager.running_queries:
        manager.cancel_action.setEnabled(False)


def clear_query_runtime(manager, tab, stop_timeout=True):
    clear_query_timers(manager, tab, stop_timeout=stop_timeout)
    clear_running_query(manager, tab)
