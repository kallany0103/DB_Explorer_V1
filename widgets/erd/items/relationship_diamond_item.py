from PySide6.QtWidgets import (
    QGraphicsPolygonItem, QGraphicsTextItem, QGraphicsItem, QMenu, QStyle
)
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPainter, QPolygonF
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF

from widgets.erd.commands import ResizeItemCommand
from widgets.erd.items.resizable import ResizableItemMixin, item_visual_scene_rect


class _DiamondLabelItem(QGraphicsTextItem):
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


class ERDRelationshipDiamondItem(QGraphicsPolygonItem, ResizableItemMixin):
    is_chen_item = True
    """
    Chen ERD Relationship Diamond (⬦).
    is_identifying=True draws a double diamond (for weak entity owner relationships).
    """

    def __init__(self, label="Relationship", is_identifying=False,
                 width=160, height=70, parent=None):
        super().__init__(parent)
        self._init_resizable()
        self.label = label
        self.is_identifying = is_identifying
        self._w = width
        self._h = height
        self.connections = []
        self.highlighted_cols = set()
        self.target_highlight = False

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)

        self.setPen(Qt.PenStyle.NoPen)
        self.setBrush(QBrush(QColor("#FFF7ED")))

        self._build_polygon()

        self._label = _DiamondLabelItem(label, self)
        self._label.setDefaultTextColor(QColor("#92400E"))
        self._label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self._label.document().contentsChanged.connect(self._sync_geometry)
        self._center_label()
        self.setZValue(1)

    def minimum_size(self):
        return QSizeF(160.0, 70.0)

    def resize_bounds(self):
        return self._bounding_box()

    def apply_size(self, width, height):
        self.prepareGeometryChange()
        self._w = width
        self._h = height
        self._build_polygon()
        self._center_label()

    def _build_polygon(self):
        w, h = self._w, self._h
        self.setPolygon(QPolygonF([
            QPointF(w / 2, 0),
            QPointF(w, h / 2),
            QPointF(w / 2, h),
            QPointF(0, h / 2),
        ]))

    def _bounding_box(self):
        return QRectF(0, 0, self._w, self._h)

    def _center_label(self):
        r = self._bounding_box()
        self._label.setTextWidth(r.width() * 0.6)
        lw = self._label.boundingRect().width()
        lh = self._label.boundingRect().height()
        self._label.setPos((r.width() - lw) / 2, (r.height() - lh) / 2)

    def _sync_geometry(self):
        if self.size_mode == "manual":
            self._label.setTextWidth(max(60, self._bounding_box().width() * 0.6))
            self._center_label()
            self._after_geometry_changed()
            return
        self._label.setTextWidth(-1)
        doc = self._label.document()
        text_w = doc.idealWidth()
        text_h = doc.size().height()
        self.apply_size(
            max(self.minimum_size().width(), text_w / 0.6 + 20),
            max(self.minimum_size().height(), text_h / 0.6 + 20),
        )
        self._after_geometry_changed()

    def auto_size(self):
        self.size_mode = "auto"
        self._sync_geometry()

    def boundingRect(self):
        pad = self.resize_padding()
        return self._bounding_box().adjusted(-pad, -pad, pad, pad)

    def shape(self):
        if self.isSelected():
            return self.resize_shape_path()
        return super().shape()

    def paint(self, painter, option, widget):
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self._w, self._h
        is_selected = (option.state & QStyle.StateFlag.State_Selected) == QStyle.StateFlag.State_Selected

        painter.setBrush(QBrush(QColor("#FFF7ED")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(self.polygon())

        # Border
        if self.target_highlight:
            border_color = QColor("#10B981") # Green for target
            border_width = 3.0
        else:
            border_color = QColor("#F59E0B") if not is_selected else QColor("#D97706")
            border_width = 2.0 if is_selected else 1.5
            
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolygon(self.polygon())

        if self.is_identifying:
            g = 6
            inner = QPolygonF([
                QPointF(w / 2, g), QPointF(w - g, h / 2),
                QPointF(w / 2, h - g), QPointF(g, h / 2),
            ])
            painter.setPen(QPen(border_color, 1.0))
            painter.drawPolygon(inner)
        self.draw_resize_handles(painter)

        if self.isUnderMouse():
            painter.setBrush(QColor("#F59E0B"))
            painter.setPen(Qt.PenStyle.NoPen)
            for px, py in [(w/2, 0), (w/2, h), (0, h/2), (w, h/2)]:
                painter.drawEllipse(QPointF(px, py), 4, 4)

    def mousePressEvent(self, event):
        handle = self.handle_at(event.pos())
        if handle:
            self.begin_resize(handle, event.scenePos())
            event.accept()
            return
        w, h = self._w, self._h
        ports = [
            (0, h/2), (w, h/2),
            (w/2, 0), (w/2, h),
        ]
        click_pos = event.pos()
        for px, py in ports:
            dx, dy = px - click_pos.x(), py - click_pos.y()
            if (dx*dx + dy*dy) < 400: # 20px radius
                # Arm pending port drag; floating connection only created
                # once cursor moves past drag threshold.
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

    def mouseDoubleClickEvent(self, event):
        self._label.setFocus()
        super().mouseDoubleClickEvent(event)

    def show_context_menu(self, screen_pos):
        import qtawesome as qta
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background:#ffffff; border:1px solid #d1d5db; border-radius:6px; padding:4px; }
            QMenu::item { padding:6px 16px; font-size:9pt; }
            QMenu::item:selected { background:#e8f0fe; color:#1a73e8; border-radius:4px; }
            QMenu::separator { height:1px; background:#e5e7eb; margin:4px 8px; }
        """)
        label = "✓ Identifying" if self.is_identifying else "Identifying Relationship"
        menu.addAction(label).triggered.connect(self._toggle_identifying)
        if self.size_mode == "manual":
            menu.addAction("Auto Size").triggered.connect(self._auto_size_from_menu)
        menu.addSeparator()
        menu.addAction(qta.icon("fa5s.trash-alt", color="#DC2626"), "Remove Diamond").triggered.connect(self._remove_self)
        menu.exec(screen_pos)

    def contextMenuEvent(self, event):
        self.show_context_menu(event.screenPos())
        event.accept()

    def _toggle_identifying(self):
        self.is_identifying = not self.is_identifying
        self.update()

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
        return self._label.toPlainText()

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
            "type": "relationship_diamond",
            "label": self.text(),
            "is_identifying": self.is_identifying,
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
