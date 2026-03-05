from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget


def create_message_view(manager, tab_content):
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    toolbar = QHBoxLayout()
    toolbar.setContentsMargins(0, 0, 0, 0)

    perf_snapshot_btn = QPushButton("Perf Snapshot")
    perf_snapshot_btn.setToolTip("Append current performance metrics to Messages")
    perf_snapshot_btn.clicked.connect(lambda: manager.dump_performance_snapshot_to_messages(tab_content))

    toolbar.addStretch()
    toolbar.addWidget(perf_snapshot_btn)

    message_view = QTextEdit()
    message_view.setObjectName("message_view")
    message_view.setReadOnly(True)

    layout.addLayout(toolbar)
    layout.addWidget(message_view)
    return container
