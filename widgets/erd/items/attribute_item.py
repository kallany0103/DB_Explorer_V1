from PySide6.QtWidgets import (
    QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsItem,
    QMenu, QStyle
)
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPainter
from PySide6.QtCore import Qt, QPointF, QSizeF

from widgets.erd.commands import ResizeItemCommand
from widgets.erd.items.resizable import ResizableItemMixin, item_visual_scene_rect


class _AttrLabelItem(QGraphicsTextItem):
    """Inline editable label for an AttributeItem."""
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


class ERDAttributeItem(QGraphicsEllipseItem, ResizableItemMixin):
    is_chen_item = True
    """
    Chen ERD Attribute shape.

    kind="normal"      → Single oval (standard attribute)
    kind="multivalued" → Double oval (can hold multiple values)
    kind="derived"     → Dashed oval (computed)
    kind="key"         → Underlined text (Primary Key)
    kind="partial"     → Dashed underlined text (Weak Entity discriminator)

    All modes support:
      - Inline editable label
      - Connection ports (top/bottom/left/right) matching ERDTableItem's API
      - Delete via context menu
    """

    GAP = 5  # inner ellipse inset for multivalued

    def __init__(self, label="Attribute", kind="normal", parent=None):
        # Default oval size
        super().__init__(0, 0, 130, 50, parent)
        self._init_resizable()

        valid_kinds = ("normal", "multivalued", "derived", "key", "partial")
        assert kind in valid_kinds, f"Unknown attribute kind: {kind!r}"
        self.kind = kind
        self.connections = []
        self.highlighted_cols = set()
        self.target_highlight = False

        # --- Flags ---
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)

        # --- Base styling ---
        self.setPen(Qt.PenStyle.NoPen)
        self.setBrush(QBrush(QColor("#F0FDF4")))  # Very light green fill

        # --- Label ---
        self._label = _AttrLabelItem(label, self)
        self._label.setDefaultTextColor(QColor("#166534"))
        
        font = QFont("Segoe UI", 9)
        if kind == "key":
            font.setUnderline(True)
        self._label.setFont(font)
        self._label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self._label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextEditorInteraction
        )
        self._label.document().contentsChanged.connect(self._sync_geometry)
        self._center_label()

        self.setZValue(1)

    def minimum_size(self):
        return QSizeF(130.0, 50.0)

    def resize_bounds(self):
        return self.rect()

    def apply_size(self, width, height):
        self.prepareGeometryChange()
        self.setRect(0, 0, width, height)
        self._center_label()

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def _center_label(self):
        r = self.rect()
        self._label.setTextWidth(r.width() - 16)
        lw = self._label.boundingRect().width()
        lh = self._label.boundingRect().height()
        self._label.setPos(
            (r.width() - lw) / 2,
            (r.height() - lh) / 2,
        )

    def _sync_geometry(self):
        if self.size_mode == "manual":
            self._label.setTextWidth(max(60, self.rect().width() - 16))
            self._center_label()
            self._after_geometry_changed()
            return
        self._label.setTextWidth(-1)
        doc = self._label.document()
        text_w = doc.idealWidth()
        text_h = doc.size().height()
        new_w = max(self.minimum_size().width(), text_w + 32)
        new_h = max(self.minimum_size().height(), text_h + 20)
        self.apply_size(new_w, new_h)
        self._after_geometry_changed()

    def auto_size(self):
        self.size_mode = "auto"
        self._sync_geometry()

    def boundingRect(self):
        pad = self.resize_padding()
        return self.rect().adjusted(-pad, -pad, pad, pad)

    def shape(self):
        if self.isSelected():
            return self.resize_shape_path()
        return super().shape()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paint(self, painter, option, widget):
        if not painter.isActive():
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        is_selected = (option.state & QStyle.StateFlag.State_Selected) == QStyle.StateFlag.State_Selected

        # Fill
        painter.setBrush(QBrush(QColor("#F0FDF4")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(r)

        # Border style based on kind
        if self.target_highlight:
            border_color = QColor("#10B981") # Green for target
            border_width = 3.0
        else:
            border_color = QColor("#22C55E") if not is_selected else QColor("#16A34A")
            border_width = 2.0 if is_selected else 1.5
            
        if self.kind == "derived":
            pen = QPen(border_color, border_width, Qt.PenStyle.DashLine)
        else:
            pen = QPen(border_color, border_width, Qt.PenStyle.SolidLine)
            
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(r)

        # Extra inner ellipse for multivalued
        if self.kind == "multivalued":
            inner_r = r.adjusted(self.GAP, self.GAP, -self.GAP, -self.GAP)
            inner_pen = QPen(border_color, 1.0, Qt.PenStyle.SolidLine)
            painter.setPen(inner_pen)
            painter.drawEllipse(inner_r)
        self.draw_resize_handles(painter)
            
        # Dashed underline for partial key (Chen notation)
        if self.kind == "partial":
            # We draw a dashed line manually under the text since QFont underline is solid
            text_rect = self._label.boundingRect()
            line_y = self._label.pos().y() + text_rect.height() - 4
            line_x1 = self._label.pos().x() + 4
            line_x2 = self._label.pos().x() + text_rect.width() - 4
            painter.setPen(QPen(QColor("#166534"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(line_x1, line_y), QPointF(line_x2, line_y))

        # Connection ports on hover
        if self.isUnderMouse():
            painter.setBrush(QColor("#22C55E"))
            painter.setPen(Qt.PenStyle.NoPen)
            cx, cy = r.center().x(), r.center().y()
            for px, py in [
                (r.left(), cy), (r.right(), cy),
                (cx, r.top()), (cx, r.bottom()),
            ]:
                painter.drawEllipse(QPointF(px, py), 4, 4)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

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
            QMenu { background: #ffffff; border: 1px solid #d1d5db; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 6px 16px; font-size: 9pt; }
            QMenu::item:selected { background: #e8f0fe; color: #1a73e8; border-radius: 4px; }
        """)
        remove_action = menu.addAction(
            qta.icon("fa5s.trash-alt", color="#DC2626"), "Remove Attribute"
        )
        remove_action.triggered.connect(self._remove_self)
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
            "type": "attribute",
            "label": self.text(),
            "kind": self.kind,
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
