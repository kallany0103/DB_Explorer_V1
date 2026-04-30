from PySide6.QtWidgets import (
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem,
    QMenu, QGraphicsDropShadowEffect, QStyle
)
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPainter
from PySide6.QtCore import Qt, QPointF, QSizeF

from widgets.erd.commands import ResizeItemCommand
from widgets.erd.items.resizable import ResizableItemMixin, item_visual_scene_rect


class _EntityLabelItem(QGraphicsTextItem):
    def focusOutEvent(self, event):
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        super().focusOutEvent(event)

    def contextMenuEvent(self, event):
        parent = self.parentItem()
        if parent and hasattr(parent, "show_context_menu"):
            parent.show_context_menu(event.screenPos())
            event.accept()
            return
        super().contextMenuEvent(event)


class ERDEntityItem(QGraphicsRectItem, ResizableItemMixin):
    is_chen_item = True
    """
    Chen ERD Entity — a single-border rectangle with an editable name label.

    This is the basic building block of Chen ERD notation.
    Unlike ERDWeakEntityItem (double border), a strong entity can be
    uniquely identified by its own attributes.

    Does NOT have column rows — use ERDTableItem for relational table representation.
    """

    CORNER_R = 4

    def __init__(self, label="Entity", width=180, height=60, parent=None):
        super().__init__(0, 0, width, height, parent)
        self._init_resizable()

        self.connections = []
        self.highlighted_cols = set()
        self.target_highlight = False

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setAcceptHoverEvents(True)

        self.setPen(Qt.PenStyle.NoPen)
        self.setBrush(QBrush(QColor("#E8F0FE")))

        # Drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(14)
        shadow.setColor(QColor(0, 0, 0, 70))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

        self._text_item = _EntityLabelItem(label, self)
        self._text_item.setDefaultTextColor(QColor("#1E3A5F"))
        self._text_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self._text_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self._text_item.document().contentsChanged.connect(self._sync_geometry)
        self._center_label()

        self.setZValue(1)

    def minimum_size(self):
        return QSizeF(180.0, 60.0)

    def resize_bounds(self):
        return self.rect()

    def apply_size(self, width, height):
        self.prepareGeometryChange()
        self.setRect(0, 0, width, height)
        self._center_label()

    def _center_label(self):
        r = self.rect()
        self._text_item.setTextWidth(r.width() - 16)
        lw = self._text_item.boundingRect().width()
        lh = self._text_item.boundingRect().height()
        self._text_item.setPos((r.width() - lw) / 2, (r.height() - lh) / 2)

    def _sync_geometry(self):
        if self.size_mode == "manual":
            self._text_item.setTextWidth(max(60, self.rect().width() - 16))
            self._center_label()
            self._after_geometry_changed()
            return
        self._text_item.setTextWidth(-1)
        doc = self._text_item.document()
        new_w = max(self.minimum_size().width(), doc.idealWidth() + 30)
        new_h = max(self.minimum_size().height(), doc.size().height() + 20)
        self.apply_size(new_w, new_h)
        self._after_geometry_changed()

    def auto_size(self):
        self.size_mode = "auto"
        self._center_label()
        self._sync_geometry()

    def boundingRect(self):
        pad = self.resize_padding()
        return self.rect().adjusted(-pad, -pad, pad, pad)

    def shape(self):
        if self.isSelected():
            return self.resize_shape_path()
        return super().shape()

    def paint(self, painter, option, widget):
        if not painter.isActive():
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        is_selected = (option.state & QStyle.StateFlag.State_Selected) == QStyle.StateFlag.State_Selected

        # Fill
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#E8F0FE")))
        painter.drawRoundedRect(r, self.CORNER_R, self.CORNER_R)

        # Single border
        if self.target_highlight:
            border_color = QColor("#10B981") # Green for target
            border_width = 3.0
        else:
            border_color = QColor("#1A73E8") if is_selected else QColor("#4A90D9")
            border_width = 2.0 if is_selected else 1.5
            
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(r, self.CORNER_R, self.CORNER_R)
        self.draw_resize_handles(painter)

        # Connection ports on hover
        if self.isUnderMouse():
            painter.setBrush(QColor("#1A73E8"))
            painter.setPen(Qt.PenStyle.NoPen)
            cx, cy = r.center().x(), r.center().y()
            for px, py in [
                (r.left(), cy), (r.right(), cy),
                (cx, r.top()), (cx, r.bottom()),
            ]:
                painter.drawEllipse(QPointF(px, py), 4, 4)

    def mousePressEvent(self, event):
        handle = self.handle_at(event.pos())
        if handle:
            self.begin_resize(handle, event.scenePos())
            event.accept()
            return
        # Check if clicking near a port (8px radius)
        r = self.rect()
        cx, cy = r.center().x(), r.center().y()
        ports = [
            (r.left(), cy), (r.right(), cy),
            (cx, r.top()), (cx, r.bottom()),
        ]
        click_pos = event.pos()
        
        for px, py in ports:
            # Use proper Euclidean distance for a perfect 20px hit circle
            dx, dy = px - click_pos.x(), py - click_pos.y()
            if (dx*dx + dy*dy) < 400: # 20px radius squared
                # Arm a pending connection drag; only promote to a real
                # floating connection if the cursor moves past the drag
                # threshold (see floating_connection.maybe_start_port_drag).
                from widgets.erd.items.floating_connection import arm_port_drag
                scene_pos = self.mapToScene(QPointF(px, py))
                arm_port_drag(self, scene_pos, relation_type="none")
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            self.update_resize(event.scenePos())
            event.accept()
            return
        if getattr(self, "_pending_port_drag", None) is not None:
            from widgets.erd.items.floating_connection import maybe_start_port_drag
            maybe_start_port_drag(self, event.scenePos())
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
        if getattr(self, "_pending_port_drag", None) is not None:
            from widgets.erd.items.floating_connection import cancel_port_drag
            cancel_port_drag(self)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def show_context_menu(self, screen_pos):
        import qtawesome as qta
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background: #ffffff; border: 1px solid #d1d5db; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 6px 16px; font-size: 9pt; }
            QMenu::item:selected { background: #e8f0fe; color: #1a73e8; border-radius: 4px; }
        """)
        menu.addAction(
            qta.icon("fa5s.trash-alt", color="#DC2626"), "Remove Entity"
        ).triggered.connect(self._remove_self)
        if self.size_mode == "manual":
            menu.addSeparator()
            menu.addAction("Auto Size").triggered.connect(self._auto_size_from_menu)
        menu.exec(screen_pos)

    def contextMenuEvent(self, event):
        self.show_context_menu(event.screenPos())
        event.accept()

    def _remove_self(self):
        scene = self.scene()
        if not scene:
            return
        self.setSelected(True)
        if hasattr(scene, "undo_stack"):
            from widgets.erd.commands import DeleteItemCommand
            scene.undo_stack.push(DeleteItemCommand(scene, [self]))
        else:
            scene.removeItem(self)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for conn in self.connections:
                conn.updatePath()
        return super().itemChange(change, value)

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

    @property
    def table_name(self):
        """Compatibility property for ERD routing and property panel."""
        return self.text()

    def text(self):
        return self._text_item.toPlainText()

    def get_column_anchor_pos(self, column_name=None, side="left"):
        r = item_visual_scene_rect(self)
        cx, cy = r.center().x(), r.center().y()
        if side == "left":
            return QPointF(r.left(), cy)
        elif side == "right":
            return QPointF(r.right(), cy)
        elif side == "top":
            return QPointF(cx, r.top())
        else:
            return QPointF(cx, r.bottom())

    def serialize_view_state(self):
        state = self.capture_geometry_state()
        state.update({
            "type": "entity",
            "label": self.text(),
        })
        return state

    def restore_view_state(self, state):
        self.apply_geometry_state(state)

    def _auto_size_from_menu(self):
        if not self.scene() or not hasattr(self.scene(), "undo_stack"):
            self.auto_size()
            return
        old_state = self.capture_geometry_state()
        self.auto_size()
        self.scene().undo_stack.push(ResizeItemCommand(self, old_state, self.capture_geometry_state()))
