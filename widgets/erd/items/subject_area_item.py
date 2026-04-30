from PySide6.QtWidgets import (
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem, QMenu, QStyle
)
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPainter
from PySide6.QtCore import Qt, QSizeF

from widgets.erd.commands import ResizeItemCommand
from widgets.erd.items.resizable import ResizableItemMixin


class _GroupTitleItem(QGraphicsTextItem):
    def focusOutEvent(self, event):
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        super().focusOutEvent(event)


class ERDSubjectAreaItem(QGraphicsRectItem, ResizableItemMixin):
    """
    Subject Area Group — a labelled semi-transparent rectangle that sits
    BEHIND all entities (z=-10).

    Usage:
      - Drag from palette to create a default-sized group.
      - Drag the SE corner handle to resize.
      - Double-click the title to edit it.
      - Right-click to change colour or delete.

    Colour palette covers 6 pastel tones that cycle automatically;
    can also be picked via context menu.
    """

    COLORS = [
        ("#DBEAFE", "#3B82F6"),   # blue
        ("#FCE7F3", "#EC4899"),   # pink
        ("#D1FAE5", "#10B981"),   # green
        ("#FEF3C7", "#F59E0B"),   # amber
        ("#EDE9FE", "#8B5CF6"),   # violet
        ("#FFE4E6", "#F43F5E"),   # rose
    ]
    _color_idx = 0  # class-level counter so each new group gets a different colour

    @property
    def table_name(self):
        """Compatibility property for ERD routing."""
        return self.text()

    def __init__(self, title="Subject Area", width=400, height=300, color_idx=None):
        super().__init__(0, 0, width, height)
        self._init_resizable()
        self.connections = []
        self.highlighted_cols = set()
        self.target_highlight = False

        if color_idx is None:
            color_idx = ERDSubjectAreaItem._color_idx % len(ERDSubjectAreaItem.COLORS)
            ERDSubjectAreaItem._color_idx += 1
        self._color_idx = color_idx
        fill, stroke = ERDSubjectAreaItem.COLORS[color_idx]
        self._fill = QColor(fill)
        self._stroke = QColor(stroke)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setZValue(-10)  # Always behind everything else

        self._apply_style()

        # --- Title label ---
        self._title = _GroupTitleItem(title, self)
        self._title.setDefaultTextColor(self._stroke.darker(130))
        self._title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._title.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self._title.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self._title.setPos(12, 8)

    def minimum_size(self):
        return QSizeF(200.0, 120.0)

    def _apply_style(self):
        fill = QColor(self._fill)
        fill.setAlpha(100)
        self.setBrush(QBrush(fill))
        self.setPen(QPen(self._stroke, 1.5, Qt.PenStyle.DashLine))

    def resize_bounds(self):
        return self.rect()

    def apply_size(self, width, height):
        self.prepareGeometryChange()
        self.setRect(0, 0, width, height)

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

        # Fill + border
        r = self.rect()
        fill = QColor(self._fill)
        fill.setAlpha(80)
        painter.setBrush(QBrush(fill))
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        
        if self.target_highlight:
            pen_color = QColor("#10B981") # Green for target
            pen_style = Qt.PenStyle.SolidLine
            pen_width = 3.0
        else:
            pen_color = self._stroke.darker(120) if is_selected else self._stroke
            pen_style = Qt.PenStyle.SolidLine if is_selected else Qt.PenStyle.DashLine
            pen_width = 2.0 if is_selected else 1.5
            
        painter.setPen(QPen(pen_color, pen_width, pen_style))
        painter.drawRoundedRect(r, 6, 6)

        self.draw_resize_handles(painter)

    # ------------------------------------------------------------------
    # Resize interaction
    # ------------------------------------------------------------------

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

    def mouseDoubleClickEvent(self, event):
        self._title.setFocus()
        super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event):
        import qtawesome as qta
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background:#ffffff; border:1px solid #d1d5db; border-radius:6px; padding:4px; }
            QMenu::item { padding:6px 16px; font-size:9pt; }
            QMenu::item:selected { background:#e8f0fe; color:#1a73e8; border-radius:4px; }
            QMenu::separator { height:1px; background:#e5e7eb; margin:4px 8px; }
        """)
        color_names = ["Blue", "Pink", "Green", "Amber", "Violet", "Rose"]
        color_menu = menu.addMenu("Change Color")
        for idx, name in enumerate(color_names):
            act = color_menu.addAction(name)
            act.triggered.connect(lambda checked=False, i=idx: self._set_color(i))
        if self.size_mode == "manual":
            menu.addAction("Auto Size").triggered.connect(self._auto_size_from_menu)
        menu.addSeparator()
        menu.addAction(
            qta.icon("fa5s.trash-alt", color="#DC2626"), "Remove Group"
        ).triggered.connect(self._remove_self)
        menu.exec(event.screenPos())
        event.accept()

    def _set_color(self, idx):
        self._color_idx = idx
        self._fill = QColor(ERDSubjectAreaItem.COLORS[idx][0])
        self._stroke = QColor(ERDSubjectAreaItem.COLORS[idx][1])
        self._apply_style()
        self._title.setDefaultTextColor(self._stroke.darker(130))
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

    def text(self):
        return self._title.toPlainText()

    def auto_size(self):
        self.size_mode = "auto"
        self._after_geometry_changed()

    def serialize_view_state(self):
        state = self.capture_geometry_state()
        state.update({
            "type": "subject_area",
            "title": self.text(),
            "color_idx": self._color_idx,
        })
        return state

    def restore_view_state(self, state):
        self._set_color(state.get("color_idx", self._color_idx))
        self.apply_geometry_state(state)

    def _auto_size_from_menu(self):
        if not self.scene() or not hasattr(self.scene(), "undo_stack"):
            self.auto_size()
            return
        old_state = self.capture_geometry_state()
        self.auto_size()
        self.scene().undo_stack.push(ResizeItemCommand(self, old_state, self.capture_geometry_state()))
