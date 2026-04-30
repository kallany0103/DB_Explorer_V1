import qtawesome as qta
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem, QMenu
from PySide6.QtGui import QBrush, QColor, QPen, QFont
from PySide6.QtCore import Qt, QSizeF

from widgets.erd.commands import ResizeItemCommand
from widgets.erd.items.resizable import ResizableItemMixin


class NoteTextItem(QGraphicsTextItem):
    def focusOutEvent(self, event):
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        super().focusOutEvent(event)

    def contextMenuEvent(self, event):
        note_item = self.parentItem()
        if note_item and hasattr(note_item, "show_context_menu"):
            note_item.show_context_menu(event.screenPos())
            event.accept()
            return
        super().contextMenuEvent(event)


class ERDNoteItem(QGraphicsRectItem, ResizableItemMixin):
    @property
    def table_name(self):
        """Compatibility property for ERD routing."""
        return self.text()

    def __init__(self, text="Note", width=220, height=120, pinned=False):
        super().__init__(0, 0, width, height)
        self._init_resizable()
        self.connections = []
        self.highlighted_cols = set()
        self._pin_icon = qta.icon("fa5s.thumbtack", color="#B45309")
        self.is_pinned = False
        self.setBrush(QBrush(QColor("#FFF7D6")))
        self.setPen(QPen(QColor("#D4B106"), 1))
        self.setZValue(1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)

        self.text_item = NoteTextItem(text, self)
        self.text_item.setDefaultTextColor(QColor("#4B5563"))
        self.text_item.setFont(QFont("Segoe UI", 10))
        self.text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.text_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.text_item.setTextWidth(width - 20)
        self.text_item.setPos(10, 8)
        self.text_item.document().contentsChanged.connect(self._sync_geometry)
        self.set_pinned(pinned)

    def minimum_size(self):
        return QSizeF(140.0, 70.0)

    def resize_bounds(self):
        return self.rect()

    def apply_size(self, width, height):
        self.prepareGeometryChange()
        self.setRect(0, 0, width, height)
        self.text_item.setTextWidth(max(120, width - 20))
        self.text_item.setPos(10, 8)

    def boundingRect(self):
        pad = self.resize_padding()
        return self.rect().adjusted(-pad, -pad, pad, pad)

    def shape(self):
        if self.isSelected():
            return self.resize_shape_path()
        return super().shape()

    def _sync_geometry(self):
        doc = self.text_item.document()
        if self.size_mode == "manual":
            self.text_item.setTextWidth(max(120, self.rect().width() - 20))
            self.text_item.setPos(10, 8)
            self._after_geometry_changed()
            return
        self.text_item.setTextWidth(max(120, self.rect().width() - 20))
        rect = doc.size()
        width = max(self.minimum_size().width(), rect.width() + 20)
        height = max(self.minimum_size().height(), rect.height() + 20)
        self.apply_size(width, height)
        self._after_geometry_changed()

    def auto_size(self):
        self.size_mode = "auto"
        self._sync_geometry()

    def set_text(self, text):
        self.text_item.setPlainText(text)
        self._sync_geometry()

    def set_pinned(self, pinned):
        self.is_pinned = bool(pinned)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not self.is_pinned)
        pen_color = QColor("#B45309") if self.is_pinned else QColor("#D4B106")
        fill_color = QColor("#FEF3C7") if self.is_pinned else QColor("#FFF7D6")
        self.setPen(QPen(pen_color, 1.2 if self.is_pinned else 1))
        self.setBrush(QBrush(fill_color))
        self.update()

    def show_context_menu(self, screen_pos):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background: #ffffff; border: 1px solid #d1d5db; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 6px 16px; font-size: 9pt; }
            QMenu::item:selected { background: #e8f0fe; color: #1a73e8; border-radius: 4px; }
            QMenu::separator { height: 1px; background: #e5e7eb; margin: 4px 8px; }
        """)

        pin_text = "Unpin Note" if self.is_pinned else "Pin Note"
        pin_action = menu.addAction(self._pin_icon, pin_text)
        pin_action.triggered.connect(lambda: self.set_pinned(not self.is_pinned))

        if self.size_mode == "manual":
            menu.addSeparator()
            menu.addAction("Auto Size").triggered.connect(self._auto_size_from_menu)

        menu.addSeparator()
        remove_icon = qta.icon("fa5s.trash-alt", color="#DC2626")
        remove_action = menu.addAction(remove_icon, "Remove Note")
        remove_action.triggered.connect(self.remove_note)
        menu.exec(screen_pos)

    def contextMenuEvent(self, event):
        self.show_context_menu(event.screenPos())
        event.accept()

    def remove_note(self):
        scene = self.scene()
        if not scene:
            return
        self.setSelected(True)
        if hasattr(scene, "undo_stack"):
            from widgets.erd.commands import DeleteItemCommand
            scene.undo_stack.push(DeleteItemCommand(scene, [self]))
        else:
            scene.removeItem(self)

    def hoverEnterEvent(self, event):
        self.update()
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event):
        self.update_resize_cursor(event.pos())
        self.update()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.clear_resize_cursor()
        self.update()
        super().hoverLeaveEvent(event)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        if self.is_pinned:
            pin_rect = self.rect().adjusted(self.rect().width() - 22, 6, -6, -self.rect().height() + 22)
            self._pin_icon.paint(painter, pin_rect.toRect())
        self.draw_resize_handles(painter)

    def mousePressEvent(self, event):
        handle = self.handle_at(event.pos())
        if handle:
            self.begin_resize(handle, event.scenePos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            self.update_resize(event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            changed = self.finish_resize()
            if changed and self.scene() and hasattr(self.scene(), "undo_stack"):
                self.scene().undo_stack.push(
                    ResizeItemCommand(self, self._resize_start_state, self.capture_geometry_state())
                )
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def apply_geometry_state(self, state):
        ResizableItemMixin.apply_geometry_state(self, state)

    def serialize_view_state(self):
        state = self.capture_geometry_state()
        state.update({
            "type": "note",
            "text": self.text(),
            "pinned": self.is_pinned,
        })
        return state

    def restore_view_state(self, state):
        self.set_pinned(state.get("pinned", False))
        self.apply_geometry_state(state)

    def _auto_size_from_menu(self):
        if not self.scene() or not hasattr(self.scene(), "undo_stack"):
            self.auto_size()
            return
        old_state = self.capture_geometry_state()
        self.auto_size()
        new_state = self.capture_geometry_state()
        self.scene().undo_stack.push(ResizeItemCommand(self, old_state, new_state))

    def text(self):
        return self.text_item.toPlainText()
