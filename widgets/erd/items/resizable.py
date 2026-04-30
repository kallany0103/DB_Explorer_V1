from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QBrush, QCursor, QPainterPath, QPen


def item_visual_scene_rect(item):
    if hasattr(item, "resize_bounds"):
        mapped_bounds = item.mapRectToScene(item.resize_bounds())
        if hasattr(mapped_bounds, "boundingRect"):
            return mapped_bounds.boundingRect()
        return QRectF(mapped_bounds)
    if hasattr(item, "rect"):
        mapped_bounds = item.mapRectToScene(item.rect())
        if hasattr(mapped_bounds, "boundingRect"):
            return mapped_bounds.boundingRect()
        return QRectF(mapped_bounds)
    return item.sceneBoundingRect()


class ResizableItemMixin:
    HANDLE_SIZE = 8.0
    HANDLE_MARGIN = 4.0
    HANDLE_ORDER = ("nw", "n", "ne", "e", "se", "s", "sw", "w")
    HANDLE_CURSORS = {
        "nw": Qt.CursorShape.SizeFDiagCursor,
        "se": Qt.CursorShape.SizeFDiagCursor,
        "ne": Qt.CursorShape.SizeBDiagCursor,
        "sw": Qt.CursorShape.SizeBDiagCursor,
        "n": Qt.CursorShape.SizeVerCursor,
        "s": Qt.CursorShape.SizeVerCursor,
        "e": Qt.CursorShape.SizeHorCursor,
        "w": Qt.CursorShape.SizeHorCursor,
    }

    def _init_resizable(self):
        self.size_mode = "auto"
        self._resize_handle = None
        self._resize_start_scene_rect = None
        self._resize_start_item_pos = None
        self._resize_start_state = None
        self._resize_hover_handle = None
        self._resizing = False
        self.setAcceptHoverEvents(True)

    def minimum_size(self):
        return QSizeF(120.0, 60.0)

    def resize_padding(self):
        return self.HANDLE_SIZE + self.HANDLE_MARGIN

    def get_size(self):
        bounds = self.resize_bounds()
        return QSizeF(bounds.width(), bounds.height())

    def resize_bounds(self):
        raise NotImplementedError

    def apply_size(self, width, height):
        raise NotImplementedError

    def apply_geometry_state(self, state):
        width = float(state.get("width", self.get_size().width()))
        height = float(state.get("height", self.get_size().height()))
        self.size_mode = state.get("size_mode", "auto")
        self.apply_size(width, height)
        self.setPos(float(state.get("x", self.pos().x())), float(state.get("y", self.pos().y())))
        if self.size_mode == "auto":
            self.auto_size()
        else:
            self._after_geometry_changed()

    def capture_geometry_state(self):
        size = self.get_size()
        pos = self.pos()
        return {
            "x": pos.x(),
            "y": pos.y(),
            "width": size.width(),
            "height": size.height(),
            "size_mode": self.size_mode,
        }

    def set_manual_size(self, width, height):
        self.size_mode = "manual"
        self.apply_size(width, height)
        self._after_geometry_changed()

    def auto_size(self):
        raise NotImplementedError

    def resize_handle_rects(self):
        rect = self.resize_bounds()
        s = self.HANDLE_SIZE
        hs = s / 2.0
        cx = rect.center().x()
        cy = rect.center().y()
        return {
            "nw": QRectF(rect.left() - hs, rect.top() - hs, s, s),
            "n": QRectF(cx - hs, rect.top() - hs, s, s),
            "ne": QRectF(rect.right() - hs, rect.top() - hs, s, s),
            "e": QRectF(rect.right() - hs, cy - hs, s, s),
            "se": QRectF(rect.right() - hs, rect.bottom() - hs, s, s),
            "s": QRectF(cx - hs, rect.bottom() - hs, s, s),
            "sw": QRectF(rect.left() - hs, rect.bottom() - hs, s, s),
            "w": QRectF(rect.left() - hs, cy - hs, s, s),
        }

    def resize_shape_path(self):
        """Return a hit-test shape that includes the resize handle padding.

        Each item should call this from its own ``shape()`` override (typically
        when the item is selected) so the resize handles, which extend outside
        ``rect()``, can actually receive hover/mouse events.
        """
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def handle_at(self, pos):
        if not self.isSelected():
            return None
        for handle, rect in self.resize_handle_rects().items():
            expanded = rect.adjusted(
                -self.HANDLE_MARGIN,
                -self.HANDLE_MARGIN,
                self.HANDLE_MARGIN,
                self.HANDLE_MARGIN,
            )
            if expanded.contains(pos):
                return handle
        return None

    def draw_resize_handles(self, painter):
        if not self.isSelected():
            return
        painter.save()
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(QPen(QColor("#1A73E8"), 1.2))
        for rect in self.resize_handle_rects().values():
            painter.drawRect(rect)
        painter.restore()

    def begin_resize(self, handle, scene_pos):
        self._resize_handle = handle
        self._resize_start_scene_rect = item_visual_scene_rect(self)
        self._resize_start_item_pos = QPointF(self.pos())
        self._resize_start_state = self.capture_geometry_state()
        self._resizing = True
        self.setCursor(QCursor(self.HANDLE_CURSORS[handle]))

    def update_resize(self, scene_pos):
        if not self._resizing or not self._resize_handle or not self._resize_start_scene_rect:
            return

        rect = QRectF(self._resize_start_scene_rect)
        min_size = self.minimum_size()
        left = rect.left()
        top = rect.top()
        right = rect.right()
        bottom = rect.bottom()

        if "e" in self._resize_handle:
            right = max(left + min_size.width(), scene_pos.x())
        if "s" in self._resize_handle:
            bottom = max(top + min_size.height(), scene_pos.y())
        if "w" in self._resize_handle:
            left = min(right - min_size.width(), scene_pos.x())
        if "n" in self._resize_handle:
            top = min(bottom - min_size.height(), scene_pos.y())

        new_rect = QRectF(QPointF(left, top), QPointF(right, bottom)).normalized()
        self.size_mode = "manual"
        self.apply_size(new_rect.width(), new_rect.height())
        self.setPos(new_rect.topLeft())
        self._after_geometry_changed()

    def finish_resize(self):
        if not self._resizing:
            return False
        self._resizing = False
        self._resize_handle = None
        self.unsetCursor()
        return self.capture_geometry_state() != self._resize_start_state

    def update_resize_cursor(self, pos):
        handle = self.handle_at(pos)
        self._resize_hover_handle = handle
        if handle:
            self.setCursor(QCursor(self.HANDLE_CURSORS[handle]))
        elif not self._resizing:
            self.unsetCursor()
        return handle

    def clear_resize_cursor(self):
        self._resize_hover_handle = None
        if not self._resizing:
            self.unsetCursor()

    def _after_geometry_changed(self):
        for conn in getattr(self, "connections", []):
            conn.updatePath()
        scene = self.scene()
        if scene and hasattr(scene, "_router_cache"):
            scene._router_cache = None
        if scene and hasattr(scene, "update_scene_rect"):
            scene.update_scene_rect()
        self.update()
