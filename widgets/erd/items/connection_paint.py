"""Crow's-foot and arrow painting helpers for ERDConnectionItem."""
import math

from PySide6.QtWidgets import QStyle
from PySide6.QtGui import QPen, QBrush, QPainterPath, QPainterPathStroker
from PySide6.QtCore import Qt, QPointF

from widgets.erd.constants import (
    CF_BAR_NEAR, CF_BAR_FAR, CF_FOOT_TIP, CF_FOOT_SPREAD, CF_FOOT_WIDTH,
    CF_CIRCLE_ONE, CF_CIRCLE_MANY, CF_CIRCLE_RADIUS,
)
from widgets.erd.items.resizable import item_visual_scene_rect


# ---------------------------------------------------------------------------
# Geometry utilities
# ---------------------------------------------------------------------------

def align_marker_origin(origin: QPointF, bridge_point: QPointF) -> QPointF:
    """Snap origin to the same axis as bridge_point (Manhattan alignment)."""
    dx = bridge_point.x() - origin.x()
    dy = bridge_point.y() - origin.y()
    if abs(dx) > abs(dy):
        return QPointF(origin.x(), bridge_point.y())
    return QPointF(bridge_point.x(), origin.y())


def find_direction_point(path, start_idx: int, forward: bool = True) -> QPointF | None:
    """Find a path element far enough from path[start_idx] to give a stable direction."""
    ref = path.elementAt(start_idx)
    ref_pt = QPointF(ref.x, ref.y)
    step = 1 if forward else -1
    idx = start_idx + step
    end = path.elementCount() if forward else -1
    while idx != end:
        elem = path.elementAt(idx)
        pt = QPointF(elem.x, elem.y)
        if (pt - ref_pt).manhattanLength() > 0.5:
            return pt
        idx += step
    return None


# ---------------------------------------------------------------------------
# Crow's-foot symbol painters (local-coordinate, painter already translated)
# ---------------------------------------------------------------------------

def _pen_for_marker(is_hovered: bool) -> QPen:
    from PySide6.QtGui import QColor
    pen = QPen(QColor("#1A73E8") if is_hovered else QColor("#5F6368"))
    pen.setWidthF(1.7 if is_hovered else 1.3)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    pen.setStyle(Qt.PenStyle.SolidLine)
    return pen


def draw_cf_symbol(painter, rel_part: str, is_hovered: bool) -> None:
    """Draw one crow's-foot symbol in local coordinates (painter already translated/rotated).
    Direction vector is assumed to point along +X axis (nx=1, ny=0)."""
    nx, ny = 1.0, 0.0
    px, py = 0.0, 1.0

    painter.setPen(_pen_for_marker(is_hovered))

    def draw_bar(offset: float) -> None:
        c = QPointF(nx * offset, ny * offset)
        painter.drawLine(
            QPointF(c.x() + px * CF_FOOT_WIDTH, c.y() + py * CF_FOOT_WIDTH),
            QPointF(c.x() - px * CF_FOOT_WIDTH, c.y() - py * CF_FOOT_WIDTH),
        )

    def draw_circle(offset: float) -> None:
        c = QPointF(nx * offset, ny * offset)
        painter.setBrush(QBrush(Qt.GlobalColor.white))
        painter.drawEllipse(c, CF_CIRCLE_RADIUS, CF_CIRCLE_RADIUS)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def draw_crows_foot(start_offset: float, spread_offset: float, spread_width: float) -> None:
        start = QPointF(nx * start_offset, ny * start_offset)
        end_c = QPointF(nx * spread_offset, ny * spread_offset)
        painter.drawLine(start, QPointF(end_c.x() + px * spread_width, end_c.y() + py * spread_width))
        painter.drawLine(start, QPointF(end_c.x() - px * spread_width, end_c.y() - py * spread_width))

    if rel_part == 'one':
        draw_bar(CF_BAR_NEAR)
        draw_bar(CF_BAR_FAR)
    elif rel_part == 'many':
        draw_crows_foot(CF_FOOT_TIP, CF_FOOT_SPREAD, CF_FOOT_WIDTH)
        draw_bar(CF_BAR_FAR)
    elif rel_part == 'zero_or_one':
        draw_bar(CF_BAR_NEAR)
        draw_circle(CF_CIRCLE_ONE)
    elif rel_part == 'zero_or_many':
        draw_crows_foot(CF_FOOT_TIP, CF_FOOT_SPREAD, CF_FOOT_WIDTH)
        draw_circle(CF_CIRCLE_MANY)


# ---------------------------------------------------------------------------
# High-level drawing helpers called from ERDConnectionItem.paint()
# ---------------------------------------------------------------------------

def draw_crows_foot(painter, origin: QPointF, bridge_point: QPointF,
                    rel_part: str, is_hovered: bool, bridge_pen: QPen) -> None:
    """Draw crow's foot for Manhattan (table) connections."""
    if rel_part == 'none':
        return
    marker_origin = align_marker_origin(origin, bridge_point)
    angle = math.atan2(bridge_point.y() - origin.y(), bridge_point.x() - origin.x())
    bridge = QPen(bridge_pen)
    bridge.setStyle(Qt.PenStyle.SolidLine)
    bridge.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    bridge.setCapStyle(Qt.PenCapStyle.FlatCap)
    painter.setPen(bridge)
    painter.drawLine(origin, bridge_point)
    painter.save()
    painter.translate(marker_origin)
    painter.rotate(math.degrees(angle))
    draw_cf_symbol(painter, rel_part, is_hovered)
    painter.restore()


def draw_crows_foot_direct(painter, origin: QPointF, next_point: QPointF,
                            rel_part: str, is_hovered: bool, bridge_pen: QPen) -> None:
    """Draw crow's foot for Chen (free-angle) connections."""
    if rel_part == 'none':
        return
    dx = next_point.x() - origin.x()
    dy = next_point.y() - origin.y()
    length = math.hypot(dx, dy)
    if length < 1e-5:
        return
    nx, ny = dx / length, dy / length
    px, py = -ny, nx
    bridge = QPen(bridge_pen)
    bridge.setStyle(Qt.PenStyle.SolidLine)
    bridge.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    bridge.setCapStyle(Qt.PenCapStyle.FlatCap)
    painter.setPen(bridge)
    painter.drawLine(origin, next_point)
    painter.setPen(_pen_for_marker(is_hovered))

    def draw_bar(offset: float) -> None:
        c = QPointF(origin.x() + nx * offset, origin.y() + ny * offset)
        painter.drawLine(
            QPointF(c.x() + px * CF_FOOT_WIDTH, c.y() + py * CF_FOOT_WIDTH),
            QPointF(c.x() - px * CF_FOOT_WIDTH, c.y() - py * CF_FOOT_WIDTH),
        )

    def draw_circle(offset: float) -> None:
        c = QPointF(origin.x() + nx * offset, origin.y() + ny * offset)
        painter.setBrush(QBrush(Qt.GlobalColor.white))
        painter.drawEllipse(c, CF_CIRCLE_RADIUS, CF_CIRCLE_RADIUS)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def draw_crows_foot_local(start_offset: float, spread_offset: float, spread_width: float) -> None:
        start = QPointF(origin.x() + nx * start_offset, origin.y() + ny * start_offset)
        end_c = QPointF(origin.x() + nx * spread_offset, origin.y() + ny * spread_offset)
        painter.drawLine(start, QPointF(end_c.x() + px * spread_width, end_c.y() + py * spread_width))
        painter.drawLine(start, QPointF(end_c.x() - px * spread_width, end_c.y() - py * spread_width))

    if rel_part == 'one':
        draw_bar(CF_BAR_NEAR)
        draw_bar(CF_BAR_FAR)
    elif rel_part == 'many':
        draw_crows_foot_local(CF_FOOT_TIP, CF_FOOT_SPREAD, CF_FOOT_WIDTH)
        draw_bar(CF_BAR_FAR)
    elif rel_part == 'zero_or_one':
        draw_bar(CF_BAR_NEAR)
        draw_circle(CF_CIRCLE_ONE)
    elif rel_part == 'zero_or_many':
        draw_crows_foot_local(CF_FOOT_TIP, CF_FOOT_SPREAD, CF_FOOT_WIDTH)
        draw_circle(CF_CIRCLE_MANY)


def draw_crows_foot_at(painter, origin: QPointF, direction_point: QPointF,
                        rel_part: str, is_hovered: bool) -> None:
    """Draw the crow's foot symbol at origin, axis-snapped toward direction_point."""
    if rel_part == 'none':
        return
    dx = direction_point.x() - origin.x()
    dy = direction_point.y() - origin.y()
    length = math.hypot(dx, dy)
    if length < 1e-5:
        return
    angle = math.atan2(dy, dx)
    snap_threshold = math.radians(2.0)
    for snap_angle in (0, math.pi / 2, math.pi, -math.pi / 2):
        if abs(angle - snap_angle) < snap_threshold:
            angle = snap_angle
            break
    painter.save()
    painter.translate(origin)
    painter.rotate(math.degrees(angle))
    draw_cf_symbol(painter, rel_part, is_hovered)
    painter.restore()


def draw_arrow(painter, P: QPointF, angle: float, is_hovered: bool) -> None:
    """Draw a simple filled arrowhead at point P facing direction angle."""
    from PySide6.QtGui import QColor
    painter.save()
    painter.translate(P)
    painter.rotate(math.degrees(angle))
    pen = QPen(QColor("#1A73E8") if is_hovered else QColor("#5F6368"))
    pen.setWidthF(2.0 if is_hovered else 1.5)
    painter.setPen(pen)
    painter.setBrush(QBrush(pen.color()))
    arrow_size = 8
    path = QPainterPath()
    path.moveTo(0, 0)
    path.lineTo(-arrow_size, arrow_size / 2)
    path.lineTo(-arrow_size, -arrow_size / 2)
    path.closeSubpath()
    painter.drawPath(path)
    painter.restore()


def draw_crows_foot_ends(painter, raw_path, RELATION_TYPES: dict,
                          relation_type: str, is_hovered: bool, bridge_pen: QPen) -> None:
    """Draw crow's foot symbols at both ends of a Manhattan connection."""
    if raw_path.elementCount() < 2:
        return
    rel_info = RELATION_TYPES.get(relation_type, RELATION_TYPES['many-to-one'])
    source_type = rel_info.get('source', 'many')
    target_type = rel_info.get('target', 'one')
    p0 = raw_path.elementAt(0)
    origin_s = QPointF(p0.x, p0.y)
    direction_s = find_direction_point(raw_path, 0, forward=True)
    if direction_s is not None:
        draw_crows_foot_at(painter, origin_s, direction_s, source_type, is_hovered)
    last_idx = raw_path.elementCount() - 1
    pn = raw_path.elementAt(last_idx)
    origin_t = QPointF(pn.x, pn.y)
    direction_t = find_direction_point(raw_path, last_idx, forward=False)
    if direction_t is not None:
        draw_crows_foot_at(painter, origin_t, direction_t, target_type, is_hovered)


def draw_chen_connection_ends(painter, raw_path, rendered_path, RELATION_TYPES: dict,
                               relation_type: str, is_hovered: bool, bridge_pen: QPen) -> None:
    """Draw crow's foot symbols at both ends of a Chen (free-angle) connection."""
    if raw_path.elementCount() < 2 or rendered_path.elementCount() < 2:
        return
    rel_info = RELATION_TYPES.get(relation_type, RELATION_TYPES['many-to-one'])
    source_type = rel_info.get('source', 'many')
    target_type = rel_info.get('target', 'one')
    raw_p0 = raw_path.elementAt(0)
    p1 = rendered_path.elementAt(1)
    draw_crows_foot_direct(
        painter, QPointF(raw_p0.x, raw_p0.y), QPointF(p1.x, p1.y),
        source_type, is_hovered, bridge_pen,
    )
    pn_1 = rendered_path.elementAt(rendered_path.elementCount() - 2)
    raw_pn = raw_path.elementAt(raw_path.elementCount() - 1)
    draw_crows_foot_direct(
        painter, QPointF(raw_pn.x, raw_pn.y), QPointF(pn_1.x, pn_1.y),
        target_type, is_hovered, bridge_pen,
    )
