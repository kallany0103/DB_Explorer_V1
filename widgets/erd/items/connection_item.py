# NOTE: This file exceeds the 500-line soft limit.  Animation/line-style logic
# lives in connection_anim.py (ERDConnectionAnimMixin) and context-menu
# construction lives in connection_menu.py (build_connection_context_menu).
# What remains here is path computation, crow's-foot rendering, hit-testing,
# serialisation, and Qt event lifecycle — concerns that are tightly coupled to
# the QGraphicsPathItem subclass and cannot be cleanly separated further.
import math
import qtawesome as qta
from PySide6.QtWidgets import (
    QGraphicsPathItem, QGraphicsItem, QGraphicsTextItem,
    QStyle,
)
from PySide6.QtGui import QPen, QColor, QPainterPath, QPainterPathStroker, QFont
from PySide6.QtCore import Qt, QPointF, QObject
from widgets.erd.constants import (
    RELATION_TYPES,
    DRAG_ENDPOINT_RADIUS,
    SELF_LOOP_STUB, SELF_LOOP_LOOP_DIST_BASE, SELF_LOOP_LOOP_DIST_STEP,
)
from widgets.erd.items.connection_anim import ERDConnectionAnimMixin
from widgets.erd.items.connection_menu import build_connection_context_menu
from widgets.erd.path_planner import ERDConnectionPathPlanner
from widgets.erd.items.connection_paint import (
    draw_crows_foot as _draw_cf,
    draw_crows_foot_direct as _draw_cf_direct,
    draw_crows_foot_at as _draw_cf_at,
    draw_crows_foot_ends as _draw_cf_ends,
    draw_chen_connection_ends as _draw_chen_ends,
    draw_arrow as _draw_arrow_fn,
    align_marker_origin as _align_marker_origin,
    find_direction_point as _find_direction_point,
)
# commands are safe to import at module level (no back-reference to this file)
from widgets.erd.commands import ChangeRelationTypeCommand, DeleteItemCommand, DetachConnectionCommand
# ERDFloatingConnectionItem is deferred below to break the mutual import cycle:
#   connection_item → floating_connection → connection_item


def _get_item_display_name(item) -> str:
    """Return a human-readable name for any ERD graphics item."""
    if hasattr(item, "table_name"):
        return item.table_name
    if hasattr(item, "text"):
        return item.text()
    if hasattr(item, "label"):
        return item.label
    return "Item"


class _ConnLabelItem(QGraphicsTextItem):
    """Inline-editable label that floats at the midpoint of a connection."""

    def __init__(self, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 9, QFont.Weight.Normal))
        self.setDefaultTextColor(QColor("#374151"))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setZValue(5)

    def focusOutEvent(self, event):
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        if not self.toPlainText().strip():
            self.hide()
        super().focusOutEvent(event)

    def paint(self, painter, option, widget):
        r = self.boundingRect().adjusted(-3, -2, 3, 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 220))
        painter.drawRoundedRect(r, 4, 4)
        super().paint(painter, option, widget)


class ERDConnectionItem(ERDConnectionAnimMixin, QObject, QGraphicsPathItem):
    # ── Relationship Types Registry (Moved to constants.py) ──
    RELATION_TYPES = RELATION_TYPES

    def __init__(
        self,
        source_item: QGraphicsItem,
        target_item: QGraphicsItem,
        source_col: str | None,
        target_col: str | None,
        is_identifying: bool = False,
        is_unique: bool = False,
        relation_name: str | None = None,
        fk_meta: dict | None = None,
    ) -> None:
        QObject.__init__(self)
        QGraphicsPathItem.__init__(self)
        self.source_item = source_item
        self.target_item = target_item
        self.source_col = source_col
        self.target_col = target_col
        self.is_identifying = is_identifying
        self.is_unique = is_unique
        self.relation_name = relation_name
        self.fk_meta = fk_meta or {}

        # --- Connection label (midpoint, hidden by default) ---
        self._label = _ConnLabelItem(self)
        self._label.hide()
        self.label_text = ""

        s_name = _get_item_display_name(source_item)
        t_name = _get_item_display_name(target_item)

        # Determine Plain-English Cardinality
        if is_unique:
            self.cardinality_desc = f"One {t_name} refers to exactly one {s_name}"
            self.cardinality_label = "One-to-One"
        else:
            self.cardinality_desc = f"One {t_name} can have many {s_name}s"
            self.cardinality_label = "Many-to-One"

        source_str = f"{s_name}.{source_col}" if source_col else s_name
        target_str = f"{t_name}.{target_col}" if target_col else t_name

        self.tooltip_text = (
            f"<b>{self.cardinality_label}</b><br/>"
            f"{self.cardinality_desc}<br/>"
            f"<code>{source_str}</code> → <code>{target_str}</code>"
        )
        if self.fk_meta.get("on_delete") or self.fk_meta.get("on_update"):
            self.tooltip_text += (
                f"<br/><small>ON DELETE {self.fk_meta.get('on_delete', 'NO ACTION')} | "
                f"ON UPDATE {self.fk_meta.get('on_update', 'NO ACTION')}</small>"
            )

        # Line styling
        pen = QPen(QColor("#5F6368"), 1.5)
        pen.setStyle(Qt.PenStyle.SolidLine)
        self.setPen(pen)

        self.relation_type = 'one-to-one' if is_unique else 'many-to-one'
        self._last_source_side = None
        self._last_target_side = None
        self.path_planner = ERDConnectionPathPlanner(self)

        self.setZValue(-1)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setToolTip(self.tooltip_text)

        self._init_anim()

        source_item.connections.append(self)
        target_item.connections.append(self)

        self.updatePath()

    # Animation/line-style methods are provided by ERDConnectionAnimMixin.

    def _is_chen_connection(self):
        return (
            getattr(self.source_item, "is_chen_item", False)
            and getattr(self.target_item, "is_chen_item", False)
        )

    @staticmethod
    def _align_marker_origin(origin: QPointF, bridge_point: QPointF) -> QPointF:
        return _align_marker_origin(origin, bridge_point)

    def _draw_crows_foot(self, painter, origin, bridge_point, rel_part, is_hovered, bridge_pen):
        _draw_cf(painter, origin, bridge_point, rel_part, is_hovered, bridge_pen)

    def _draw_crows_foot_direct(self, painter, origin, next_point, rel_part, is_hovered, bridge_pen):
        _draw_cf_direct(painter, origin, next_point, rel_part, is_hovered, bridge_pen)

    def _draw_arrow(self, painter, P, angle, is_hovered):
        _draw_arrow_fn(painter, P, angle, is_hovered)

    def boundingRect(self):
        return QGraphicsPathItem.boundingRect(self).adjusted(-40, -40, 40, 40)

    def shape(self):
        base_path = self.path()
        if base_path.isEmpty():
            return QPainterPath()

        stroker = QPainterPathStroker()
        stroker.setWidth(12.0)
        stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        hit_shape = stroker.createStroke(base_path)
        return hit_shape.united(base_path)

    # ------------------------------------------------------------------
    # Hover
    # ------------------------------------------------------------------

    def hoverEnterEvent(self, event):
        if hasattr(self.source_item, 'highlighted_cols'):
            self.source_item.highlighted_cols.add(self.source_col)
        if hasattr(self.target_item, 'highlighted_cols'):
            self.target_item.highlighted_cols.add(self.target_col)
        self.source_item.update()
        self.target_item.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if hasattr(self.source_item, 'highlighted_cols'):
            if self.source_col in self.source_item.highlighted_cols:
                self.source_item.highlighted_cols.remove(self.source_col)
        if hasattr(self.target_item, 'highlighted_cols'):
            if self.target_col in self.target_item.highlighted_cols:
                self.target_item.highlighted_cols.remove(self.target_col)
        self.source_item.update()
        self.target_item.update()
        super().hoverLeaveEvent(event)

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        path = self.path()
        if path.elementCount() >= 2:
            p0 = path.elementAt(0)
            pn = path.elementAt(path.elementCount() - 1)
            dist_start = (event.scenePos() - self.mapToScene(QPointF(p0.x, p0.y))).manhattanLength()
            dist_end = (event.scenePos() - self.mapToScene(QPointF(pn.x, pn.y))).manhattanLength()

            if dist_start < DRAG_ENDPOINT_RADIUS:
                self._drag_side = "start"
                self._current_mouse_pos = event.scenePos()
                self.setSelected(True)
                event.accept()
                return
            elif dist_end < DRAG_ENDPOINT_RADIUS:
                self._drag_side = "end"
                self._current_mouse_pos = event.scenePos()
                self.setSelected(True)
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, '_drag_side', None):
            self._current_mouse_pos = event.scenePos()
            self.updatePath()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Double-click opens inline label editor at midpoint."""
        self._label.show()
        self._update_label_pos()
        self._label.setFocus()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if getattr(self, '_drag_side', None):
            from widgets.erd.items.floating_connection import ERDFloatingConnectionItem  # deferred: circular import guard
            if self._drag_side == "start":
                p1 = event.scenePos()
                p2 = self.target_item.get_column_anchor_pos(self.target_col, self._last_target_side or "left")
                trigger_handle = "start"
            else:
                p1 = self.source_item.get_column_anchor_pos(self.source_col, self._last_source_side or "right")
                p2 = event.scenePos()
                trigger_handle = "end"

            self._drag_side = None

            from widgets.erd.widget import ERDWidget  # deferred: avoids circular import at module level
            widget = self.scene().parent()
            while widget and not isinstance(widget, ERDWidget):
                widget = widget.parent()

            floating = ERDFloatingConnectionItem(self.relation_type)
            floating.set_handles(p1, p2)

            # Preserve the anchor for the end that wasn't detached
            if trigger_handle == "start":
                floating.end_handle.anchored_item = self.target_item
                floating.end_handle.anchored_col = self.target_col
            else:
                floating.start_handle.anchored_item = self.source_item
                floating.start_handle.anchored_col = self.source_col

            cmd = DetachConnectionCommand(widget, self, floating)
            self.scene().undo_stack.push(cmd)

            floating.check_anchors()

            event.accept()
            return

        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Path computation & Trimming
    # ------------------------------------------------------------------

    @staticmethod
    def _path_to_points(path):
        points = []
        for i in range(path.elementCount()):
            elem = path.elementAt(i)
            point = QPointF(elem.x, elem.y)
            if not points or (point - points[-1]).manhattanLength() >= 0.5:
                points.append(point)
        return points

    @staticmethod
    def _snap_coord_for_pen(value, pen_width):
        rounded_width = round(pen_width)
        if abs(pen_width - rounded_width) < 0.01:
            return float(round(value))
        return float(round(value) + 0.5)

    @classmethod
    def _snap_point_for_pen(cls, point, pen_width):
        return QPointF(
            cls._snap_coord_for_pen(point.x(), pen_width),
            cls._snap_coord_for_pen(point.y(), pen_width),
        )

    @staticmethod
    def _segment_length(start, end):
        return abs(end.x() - start.x()) + abs(end.y() - start.y())

    @classmethod
    def _point_along_segment(cls, start, end, distance):
        seg_len = cls._segment_length(start, end)
        if seg_len <= 0.5:
            return QPointF(start)

        ratio = max(0.0, min(1.0, distance / seg_len))
        if abs(start.x() - end.x()) < 0.5:
            return QPointF(start.x(), start.y() + (end.y() - start.y()) * ratio)
        return QPointF(start.x() + (end.x() - start.x()) * ratio, start.y())

    @classmethod
    def _trim_orthogonal_points(cls, points, start_trim, end_trim):
        if len(points) < 2:
            return []

        total_length = 0.0
        for i in range(len(points) - 1):
            total_length += cls._segment_length(points[i], points[i + 1])

        if total_length <= start_trim + end_trim + 5:
            return []

        remaining_start = start_trim
        start_index = 0
        start_point = QPointF(points[0])
        while start_index < len(points) - 1:
            seg_start = points[start_index]
            seg_end = points[start_index + 1]
            seg_len = cls._segment_length(seg_start, seg_end)
            if seg_len <= 0.5:
                start_index += 1
                start_point = QPointF(seg_end)
                continue
            if remaining_start < seg_len:
                start_point = cls._point_along_segment(seg_start, seg_end, remaining_start)
                break
            remaining_start -= seg_len
            start_index += 1
            start_point = QPointF(seg_end)

        remaining_end = end_trim
        end_index = len(points) - 1
        end_point = QPointF(points[-1])
        while end_index > 0:
            seg_start = points[end_index - 1]
            seg_end = points[end_index]
            seg_len = cls._segment_length(seg_start, seg_end)
            if seg_len <= 0.5:
                end_index -= 1
                end_point = QPointF(seg_start)
                continue
            if remaining_end < seg_len:
                end_point = cls._point_along_segment(seg_end, seg_start, remaining_end)
                break
            remaining_end -= seg_len
            end_index -= 1
            end_point = QPointF(seg_start)

        trimmed = [start_point]
        for i in range(start_index + 1, end_index):
            trimmed.append(QPointF(points[i]))
        trimmed.append(end_point)

        deduped = [trimmed[0]]
        for point in trimmed[1:]:
            if (point - deduped[-1]).manhattanLength() >= 0.5:
                deduped.append(point)

        if len(deduped) < 2:
            return []

        collapsed = [deduped[0]]
        for point in deduped[1:]:
            if len(collapsed) >= 2:
                prev = collapsed[-1]
                prev_prev = collapsed[-2]
                is_horizontal = abs(prev_prev.y() - prev.y()) < 0.5 and abs(prev.y() - point.y()) < 0.5
                is_vertical = abs(prev_prev.x() - prev.x()) < 0.5 and abs(prev.x() - point.x()) < 0.5
                if is_horizontal or is_vertical:
                    collapsed[-1] = point
                    continue
            collapsed.append(point)

        return collapsed if len(collapsed) >= 2 else []

    @classmethod
    def _build_path_from_points(cls, points, pen_width=None, snap=False):
        if len(points) < 2:
            return QPainterPath()

        path = QPainterPath()
        normalized = []
        for point in points:
            normalized_point = point
            if snap and pen_width is not None:
                normalized_point = cls._snap_point_for_pen(point, pen_width)
            if not normalized or (normalized_point - normalized[-1]).manhattanLength() >= 0.5:
                normalized.append(normalized_point)

        if len(normalized) < 2:
            return QPainterPath()

        path.moveTo(normalized[0])
        for point in normalized[1:]:
            path.lineTo(point)
        return path

    @classmethod
    def _get_rendered_path(cls, path, pen_width, snap):
        if not snap:
            return path
        return cls._build_path_from_points(
            cls._path_to_points(path),
            pen_width=pen_width,
            snap=True,
        )

    def _get_trimmed_path(self, path, start_trim=20, end_trim=20):
        """Return a trimmed orthogonal path without resampling elbows into curves."""
        points = self._path_to_points(path)
        trimmed_points = self._trim_orthogonal_points(points, start_trim, end_trim)
        return self._build_path_from_points(trimmed_points)

    def updatePath(self) -> None:
        if getattr(self, '_drag_side', None):
            path = QPainterPath()
            if self._drag_side == "start":
                p1_scene = self._current_mouse_pos
                p2_scene = self.target_item.get_column_anchor_pos(self.target_col, self._last_target_side or "left")
                start_side = "none" # Mouse side
                end_side = self._last_target_side or "left"
            else:
                p1_scene = self.source_item.get_column_anchor_pos(self.source_col, self._last_source_side or "right")
                p2_scene = self._current_mouse_pos
                start_side = self._last_source_side or "right"
                end_side = "none" # Mouse side

            p1 = self.mapFromScene(p1_scene)
            p2 = self.mapFromScene(p2_scene)
            
            path.moveTo(p1)
            # Orthogonal routing for drag
            if start_side in ("left", "right") or end_side in ("left", "right"):
                mid_x = (p1.x() + p2.x()) / 2
                path.lineTo(mid_x, p1.y())
                path.lineTo(mid_x, p2.y())
            else:
                mid_y = (p1.y() + p2.y()) / 2
                path.lineTo(p1.x(), mid_y)
                path.lineTo(p2.x(), mid_y)
            path.lineTo(p2)
            
            self.prepareGeometryChange()
            self.setPath(path)
            self.update()
            return

        if getattr(self, "_updating", False):
            return
        self._updating = True

        try:
            if self.source_item == self.target_item:
                self.updateSelfLoopPath()
                return

            best_points, best_s_side, best_t_side = self.path_planner.compute_best_path()
            self._last_source_side = best_s_side
            self._last_target_side = best_t_side

            path = QPainterPath()
            if best_points:
                path.moveTo(best_points[0])
                for i in range(1, len(best_points)):
                    path.lineTo(best_points[i])

            self.prepareGeometryChange()
            self.setPath(path)

        finally:
            self._updating = False

    def updateSelfLoopPath(self):
        col_idx = -1
        for i, col in enumerate(self.source_item.columns):
            if col['name'] == self.source_col:
                col_idx = i
                break

        a1 = self.source_item.get_column_anchor_pos(self.source_col, "right")
        a2 = self.target_item.get_column_anchor_pos(self.target_col, "right")

        path = QPainterPath()
        path.moveTo(a1)

        s_stub = QPointF(a1.x() + SELF_LOOP_STUB, a1.y())
        t_stub = QPointF(a2.x() + SELF_LOOP_STUB, a2.y())
        path.lineTo(s_stub)

        loop_dist = SELF_LOOP_LOOP_DIST_BASE + (col_idx * SELF_LOOP_LOOP_DIST_STEP)
        cp1 = QPointF(s_stub.x() + loop_dist, s_stub.y())
        cp2 = QPointF(t_stub.x() + loop_dist, t_stub.y())
        path.cubicTo(cp1, cp2, t_stub)
        path.lineTo(a2)

        self.setPath(path)

    # ------------------------------------------------------------------
    # Label helpers
    # ------------------------------------------------------------------

    def _update_label_pos(self):
        path = self.path()
        if path.isEmpty():
            return
        mid = path.pointAtPercent(0.5)
        br = self._label.boundingRect()
        self._label.setPos(mid - QPointF(br.width() / 2, br.height() / 2))

    def set_label(self, text: str) -> None:
        """Programmatically set (or clear) the connection label."""
        self.label_text = text
        if text:
            self._label.setPlainText(text)
            self._label.show()
        else:
            self._label.hide()
        self._update_label_pos()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paint(self, painter, option, widget):
        if not painter.isActive():
            return
            
        path = self.path()
        if path.elementCount() < 2:
            return

        is_hovered = option.state & QStyle.StateFlag.State_MouseOver
        
        # Get relationship info for trimming
        rel_info = self.RELATION_TYPES.get(self.relation_type, self.RELATION_TYPES['many-to-one'])
        source_type = rel_info.get('source', 'many')
        target_type = rel_info.get('target', 'one')
        
        # Draw the full line - symbols will overlay on top at the endpoints
        # No trimming needed: bars are perpendicular and crow's feet diagonals
        # don't conflict with the line direction, so they overlay correctly.
        draw_path = path

        pen = self._apply_line_style_to_pen(QPen(self.pen()), hovered=bool(is_hovered))

        should_snap = (
            hasattr(self.source_item, "table_name")
            and hasattr(self.target_item, "table_name")
            and not getattr(self.source_item, "is_chen_item", False)
            and not getattr(self.target_item, "is_chen_item", False)
        )
        display_path = self._get_rendered_path(draw_path, pen.widthF(), should_snap)

        # 1. Draw base line — faded when animated (draw.io style)
        if self._is_animated:
            faded_pen = QPen(pen)
            c = faded_pen.color()
            c.setAlpha(60)
            faded_pen.setColor(c)
            painter.setPen(faded_pen)
        else:
            painter.setPen(pen)
        painter.drawPath(display_path)

        # 2. Draw Animation Overlay — marching dashes in the line's own color
        if self._is_animated:
            anim_path = display_path
            if not anim_path.isEmpty():
                anim_pen = QPen(pen.color())  # line's own color, not hard-coded blue
                anim_pen.setWidthF(pen.widthF() + 0.5)
                anim_pen.setDashPattern([8.0, 6.0])  # draw.io marching-dash ratio
                anim_pen.setCapStyle(Qt.PenCapStyle.RoundCap)

                if self._flow_mode == "bidirectional":
                    anim_pen.setDashOffset(self._dash_offset)
                    painter.setPen(anim_pen)
                    painter.drawPath(anim_path)
                    anim_pen.setDashOffset(-self._dash_offset)
                    painter.setPen(anim_pen)
                    painter.drawPath(anim_path)
                elif self._flow_mode == "backward":
                    anim_pen.setDashOffset(-self._dash_offset)
                    painter.setPen(anim_pen)
                    painter.drawPath(anim_path)
                else:  # forward (default)
                    anim_pen.setDashOffset(self._dash_offset)
                    painter.setPen(anim_pen)
                    painter.drawPath(anim_path)

        painter.setPen(pen)  # restore full pen for crow's foot / arrow drawing

        # 3. Draw Crow's Foot Ends
        if self._is_chen_connection():
            self._draw_chen_connection_ends(painter, path, display_path, is_hovered, pen)
        else:
            self._draw_crows_foot_ends(painter, path, display_path, is_hovered, pen)

        # 4. Draw Flow Arrows (ONLY if no crow's foot notation)
        if self._flow_mode in ("forward", "bidirectional") and target_type == 'none':
            # Arrow at target end
            pn = display_path.elementAt(display_path.elementCount() - 1)
            pn_1 = display_path.elementAt(display_path.elementCount() - 2)
            angle = math.atan2(pn.y - pn_1.y, pn.x - pn_1.x)
            self._draw_arrow(painter, QPointF(pn.x, pn.y), angle, is_hovered)
            
        if self._flow_mode in ("backward", "bidirectional") and source_type == 'none':
            # Arrow at source end
            p0 = display_path.elementAt(0)
            p1 = display_path.elementAt(1)
            angle = math.atan2(p0.y - p1.y, p0.x - p1.x)
            self._draw_arrow(painter, QPointF(p0.x, p0.y), angle, is_hovered)

        # Keep label positioned at midpoint
        self._update_label_pos()

    def _draw_crows_foot_ends(self, painter, raw_path, rendered_path, is_hovered, bridge_pen):
        _draw_cf_ends(painter, raw_path, self.RELATION_TYPES, self.relation_type, is_hovered, bridge_pen)

    @staticmethod
    def _find_direction_point(path, start_idx: int, forward: bool = True):
        return _find_direction_point(path, start_idx, forward)

    def _draw_crows_foot_at(self, painter, origin, direction_point, rel_part, is_hovered, bridge_pen):
        _draw_cf_at(painter, origin, direction_point, rel_part, is_hovered)

    def _draw_chen_connection_ends(self, painter, raw_path, rendered_path, is_hovered, bridge_pen):
        _draw_chen_ends(painter, raw_path, rendered_path, self.RELATION_TYPES, self.relation_type, is_hovered, bridge_pen)

    # ------------------------------------------------------------------
    # Relation type management
    # ------------------------------------------------------------------

    def _apply_relation_type(self, type_key: str) -> None:
        self.relation_type = type_key
        rel_info = self.RELATION_TYPES[type_key]
        self.cardinality_label = rel_info['label']
        
        s_name = _get_item_display_name(self.source_item)
        t_name = _get_item_display_name(self.target_item)
        
        source_str = f"{s_name}.{self.source_col}" if self.source_col else s_name
        target_str = f"{t_name}.{self.target_col}" if self.target_col else t_name

        self.tooltip_text = (
            f"<b>{self.cardinality_label}</b><br/>"
            f"<code>{source_str}</code> → "
            f"<code>{target_str}</code>"
        )
        self.setToolTip(self.tooltip_text)
        self.is_unique = type_key in ('one-to-one',)
        self.prepareGeometryChange()
        self.update()

    def set_relation_type(self, type_key: str) -> None:
        if type_key not in self.RELATION_TYPES or type_key == self.relation_type:
            return

        if self.scene() and hasattr(self.scene(), 'undo_stack'):
            cmd = ChangeRelationTypeCommand(self, self.relation_type, type_key)
            self.scene().undo_stack.push(cmd)
        else:
            self._apply_relation_type(type_key)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event):
        menu = build_connection_context_menu(self)
        menu.exec(event.screenPos())

    def _remove_self(self) -> None:
        scene = self.scene()
        if not scene:
            return
        self.setSelected(True)
        if hasattr(scene, "undo_stack"):
            scene.undo_stack.push(DeleteItemCommand(scene, [self]))
        else:
            scene.removeItem(self)

    def _open_label_editor(self):
        self._label.show()
        self._update_label_pos()
        self._label.setFocus()

    # ------------------------------------------------------------------
    # Detach
    # ------------------------------------------------------------------

    def detach_relationship(self) -> None:
        if not self.scene() or not hasattr(self.scene(), 'undo_stack'):
            return

        from widgets.erd.items.floating_connection import ERDFloatingConnectionItem  # deferred: circular import guard
        from widgets.erd.widget import ERDWidget  # deferred: avoids circular import at module level
        widget = self.scene().parent()
        while widget and not isinstance(widget, ERDWidget):
            widget = widget.parent()

        floating = ERDFloatingConnectionItem(self.relation_type)
        p1 = self.source_item.get_column_anchor_pos(self.source_col, self._last_source_side or "right")
        p2 = self.target_item.get_column_anchor_pos(self.target_col, self._last_target_side or "left")
        floating.set_handles(p1, p2)

        cmd = DetachConnectionCommand(widget, self, floating)
        self.scene().undo_stack.push(cmd)

        floating.check_anchors()
