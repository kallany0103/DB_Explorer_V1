from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QStyle

class NotificationWidget(QWidget):
    closed = pyqtSignal(QWidget)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.ToolTip
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("notificationWidget")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        self.icon_label = QLabel()
        self.message_label = QLabel()
        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("notificationCloseButton")
        self.close_button.setFixedSize(20, 20)
        self.close_button.clicked.connect(self.close_widget)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.message_label)
        layout.addStretch()
        layout.addWidget(self.close_button)

    def show_message(self, message, is_error=False):
        self.message_label.setText(message)
        if is_error:
            self.setProperty("isError", True)
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)
        else:
            self.setProperty("isError", False)
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
        self.icon_label.setPixmap(icon.pixmap(16, 16))
        self.style().unpolish(self)
        self.style().polish(self)
        self.adjustSize()
        self.show()

    def close_widget(self):
        self.closed.emit(self)
        self.close()


class NotificationManager:
    def __init__(self, parent_widget):
        self.parent = parent_widget
        self.notifications = []
        self.spacing = 10
        self.margin = 15

    def show_message(self, message, is_error=False):
        notification = NotificationWidget(self.parent)
        notification.closed.connect(self.on_notification_closed)
        self.notifications.insert(0, notification)
        notification.show_message(message, is_error)
        self.reposition_notifications()

    def on_notification_closed(self, notification_widget):
        try:
            self.notifications.remove(notification_widget)
        except ValueError:
            pass
        self.reposition_notifications()

    def reposition_notifications(self):
        if not self.parent:
            return
        parent_rect = self.parent.geometry()
        status_bar_height = 0
        if hasattr(self.parent, 'statusBar') and self.parent.statusBar():
            status_bar_height = self.parent.statusBar().height()
        y = parent_rect.height() - status_bar_height - self.margin
        for notification in self.notifications:
            y -= notification.height()
            x = parent_rect.width() - notification.width() - self.margin
            notification.move(x, y)
            y -= self.spacing

