from PySide6.QtWidgets import QLabel, QTextEdit


def _get_message_view(tab):
    if not tab:
        return None
    return tab.findChild(QTextEdit, "message_view")


def _get_tab_status_label(tab):
    if not tab:
        return None
    return tab.findChild(QLabel, "tab_status_label")


def set_global_status(manager, text):
    if hasattr(manager, "status_message_label") and manager.status_message_label:
        manager.status_message_label.setText(str(text or ""))


def set_tab_status(tab, text):
    label = _get_tab_status_label(tab)
    if label:
        label.setText(str(text or ""))


def replace_message(tab, text):
    message_view = _get_message_view(tab)
    if not message_view:
        return
    message_view.setText(str(text or ""))
    message_view.verticalScrollBar().setValue(message_view.verticalScrollBar().maximum())


def append_error_message(tab, error_message):
    message_view = _get_message_view(tab)
    if not message_view:
        return
        
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    msg = f"[{timestamp}]  ERROR:\n\n{error_message}"
    
    message_view.setPlainText(msg)
    message_view.verticalScrollBar().setValue(message_view.verticalScrollBar().maximum())
