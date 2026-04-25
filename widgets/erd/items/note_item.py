from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem
from PySide6.QtGui import QBrush, QColor, QPen, QFont
from PySide6.QtCore import Qt


class ERDNoteItem(QGraphicsRectItem):
    def __init__(self, text="Note", width=220, height=120):
        super().__init__(0, 0, width, height)
        self.setBrush(QBrush(QColor("#FFF7D6")))
        self.setPen(QPen(QColor("#D4B106"), 1))
        self.setZValue(1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)

        self.text_item = QGraphicsTextItem(text, self)
        self.text_item.setDefaultTextColor(QColor("#4B5563"))
        self.text_item.setFont(QFont("Segoe UI", 10))
        self.text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.text_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.text_item.setTextWidth(width - 20)
        self.text_item.setPos(10, 8)
        self.text_item.document().contentsChanged.connect(self._sync_geometry)

    def _sync_geometry(self):
        doc = self.text_item.document()
        self.text_item.setTextWidth(max(120, self.rect().width() - 20))
        rect = doc.size()
        width = max(140, rect.width() + 20)
        height = max(70, rect.height() + 20)
        self.prepareGeometryChange()
        self.setRect(0, 0, width, height)
        self.text_item.setTextWidth(width - 20)
        self.text_item.setPos(10, 8)

    def set_text(self, text):
        self.text_item.setPlainText(text)
        self._sync_geometry()

    def text(self):
        return self.text_item.toPlainText()
