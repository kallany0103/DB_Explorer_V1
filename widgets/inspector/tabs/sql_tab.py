from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QScrollArea


class SqlTab(QWidget):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.sql_text = data.get("sql", "") if isinstance(data, dict) else str(data)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.editor = QTextEdit()
        self.editor.setObjectName("propertySqlEditor")
        self.editor.setReadOnly(True)
        self.editor.setPlainText(self.sql_text)
        layout.addWidget(self.editor)
        layout.addStretch()

        self._update_editor_geometry()

    def _find_parent_scroll_area(self):
        curr = self.parentWidget()
        while curr:
            if isinstance(curr, QScrollArea):
                return curr
            curr = curr.parentWidget()
        return None

    def _update_editor_geometry(self):
        fm = self.editor.fontMetrics()
        line_h = fm.lineSpacing() or 18
        lines = max(1, len(self.sql_text.splitlines()))

        doc = self.editor.document()
        doc_h = doc.documentLayout().documentSize().height() if doc else 0

        est_h = max(int(doc_h) + 28, (lines * line_h) + 48)

        parent_scroll = self._find_parent_scroll_area()
        if parent_scroll and parent_scroll.viewport().height() > 100:
            avail_h = max(200, parent_scroll.viewport().height() - 60)
        else:
            avail_h = 550

        final_h = max(80, min(est_h, avail_h))
        self.editor.setFixedHeight(final_h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_editor_geometry()
