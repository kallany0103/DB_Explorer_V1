"""Manhattan-path planner for ERD connections: slot assignment, obstacle avoidance, orthogonalisation."""
from PySide6.QtCore import QPointF

from widgets.erd.items.table_item import ERDTableItem
from widgets.erd.items.resizable import item_visual_scene_rect
from widgets.erd.routing import get_chen_boundary_anchor, get_dynamic_anchor


class ERDConnectionPathPlanner:
    def __init__(self, connection_item):
        self.connection_item = connection_item

    def _relationship_key(self, conn=None):
        """Stable key for a pair of items to ensure they share a routing slot."""
        relation_conn = conn or self.connection_item
        def get_name(it):
            if hasattr(it, "label"):
                return it.label
            if hasattr(it, "table_name"):
                return it.table_name
            return str(id(it))
        names = sorted([
            get_name(relation_conn.source_item),
            get_name(relation_conn.target_item)
        ])
        return "-".join(names)

    def _is_chen_connection(self) -> bool:
        """Returns True if both ends of the connection are Chen ERD elements."""
        s_item = self.connection_item.source_item
        t_item = self.connection_item.target_item
        return (getattr(s_item, "is_chen_item", False) and
                getattr(t_item, "is_chen_item", False))

    def _preferred_side(self, item, other_item) -> str:
        item_rect = item_visual_scene_rect(item)
        other_rect = item_visual_scene_rect(other_item)
        dx = other_rect.center().x() - item_rect.center().x()
        dy = other_rect.center().y() - item_rect.center().y()
        if abs(dx) >= abs(dy):
            return "right" if dx >= 0 else "left"
        return "bottom" if dy >= 0 else "top"

    def _get_side_relationship_keys(self, item, side) -> list:
        keys = []
        seen: set = set()
        for conn in item.connections:
            if conn.source_item == item:
                other_item = conn.target_item
                conn_side = getattr(conn, "_last_source_side", None)
            else:
                other_item = conn.source_item
                conn_side = getattr(conn, "_last_target_side", None)
            if conn_side is None:
                conn_side = self._preferred_side(item, other_item)
            if conn_side != side:
                continue
            rel_key = self._relationship_key(conn)
            if rel_key in seen:
                continue
            seen.add(rel_key)
            keys.append(rel_key)
        keys.sort()
        return keys

    def _apply_slot_offset(self, item, side: str, anchor: QPointF) -> QPointF:
        rel_key = self._relationship_key()
        keys = self._get_side_relationship_keys(item, side)
        if rel_key not in keys:
            keys.append(rel_key)
            keys.sort()
        if len(keys) <= 1:
            return anchor
        slot_index = keys.index(rel_key)
        centered_index = slot_index - ((len(keys) - 1) / 2.0)
        spacing = 22.0
        offset = centered_index * spacing
        rect = item_visual_scene_rect(item)
        margin = 12.0
        if side in ("left", "right"):
            y = max(rect.top() + margin, min(rect.bottom() - margin, anchor.y() + offset))
            return QPointF(anchor.x(), y)
        x = max(rect.left() + margin, min(rect.right() - margin, anchor.x() + offset))
        return QPointF(x, anchor.y())

    def _get_base_anchor(self, item, side: str) -> QPointF:
        """Return a side anchor that prefers the actual related column row when available."""
        if item == self.connection_item.source_item:
            col_name = self.connection_item.source_col
        elif item == self.connection_item.target_item:
            col_name = self.connection_item.target_col
        else:
            col_name = None
        if col_name and hasattr(item, "get_column_anchor_pos"):
            return item.get_column_anchor_pos(col_name, side)
        return get_dynamic_anchor(item, side)

    def _get_anchor_with_slot(self, item, other_item, side: str) -> QPointF:
        anchor = self._get_base_anchor(item, side)
        return self._apply_slot_offset(item, side, anchor)

    def _orthogonalize_end_segments(self, points: list, s_side: str, t_side: str) -> list:
        if not points or len(points) < 2:
            return points
        pts = list(points)
        stub_px = 2.0
        p0, pn = pts[0], pts[-1]

        source_stub = _side_stub(p0, s_side, stub_px)
        target_stub = _side_stub(pn, t_side, stub_px)

        if len(pts) == 2:
            expanded = [p0, source_stub, target_stub, pn]
            return _dedup_points(expanded)

        middle = pts[1:-1]
        expanded = [p0, source_stub] + middle + [target_stub, pn]
        expanded = _fix_source_hinge(expanded, s_side, source_stub)
        expanded = _fix_target_hinge(expanded, t_side, target_stub, s_side, source_stub)
        return _dedup_points(expanded)

    def _force_manhattan(self, points: list) -> list:
        if not points or len(points) < 2:
            return points
        normalized = [points[0]]
        for point in points[1:]:
            prev = normalized[-1]
            dx = abs(point.x() - prev.x())
            dy = abs(point.y() - prev.y())
            if dx > 0.5 and dy > 0.5:
                normalized.append(QPointF(point.x(), prev.y()))
            normalized.append(point)
        return _dedup_points(normalized)

    def _is_source_direction_valid(self, start: QPointF, nxt: QPointF, side: str) -> bool:
        eps = 0.5
        if side == "left":
            return nxt.x() <= start.x() - eps
        if side == "right":
            return nxt.x() >= start.x() + eps
        if side == "top":
            return nxt.y() <= start.y() - eps
        return nxt.y() >= start.y() + eps

    def _is_target_direction_valid(self, prev: QPointF, end: QPointF, side: str) -> bool:
        eps = 0.5
        if side == "left":
            return prev.x() <= end.x() - eps
        if side == "right":
            return prev.x() >= end.x() + eps
        if side == "top":
            return prev.y() <= end.y() - eps
        return prev.y() >= end.y() + eps

    def _segment_hits_rect(self, p1: QPointF, p2: QPointF, rect) -> bool:
        eps = 0.5
        if abs(p1.x() - p2.x()) < eps:
            x = p1.x()
            if rect.left() + eps < x < rect.right() - eps:
                y1, y2 = min(p1.y(), p2.y()), max(p1.y(), p2.y())
                return y2 > rect.top() + eps and y1 < rect.bottom() - eps
            return False
        if abs(p1.y() - p2.y()) < eps:
            y = p1.y()
            if rect.top() + eps < y < rect.bottom() - eps:
                x1, x2 = min(p1.x(), p2.x()), max(p1.x(), p2.x())
                return x2 > rect.left() + eps and x1 < rect.right() - eps
        return False

    def _path_hits_obstacles(self, points: list) -> bool:
        scene = self.connection_item.scene()
        if not scene:
            return False
        for item in scene.items():
            if not isinstance(item, ERDTableItem):
                continue
            if item in (self.connection_item.source_item, self.connection_item.target_item):
                continue
            rect = item_visual_scene_rect(item).adjusted(2, 2, -2, -2)
            for i in range(len(points) - 1):
                if self._segment_hits_rect(points[i], points[i + 1], rect):
                    return True
        return False

    def _get_pretty_manhattan_path(self, start: QPointF, end: QPointF, s_side: str, t_side: str):
        candidates = _build_path_candidates(start, end, s_side, t_side)
        for cand in candidates:
            cand = self._force_manhattan(cand)
            if len(cand) < 2:
                continue
            if not self._is_source_direction_valid(cand[0], cand[1], s_side):
                continue
            if not self._is_target_direction_valid(cand[-2], cand[-1], t_side):
                continue
            if self._path_hits_obstacles(cand):
                continue
            return cand
        return None

    def _get_pair_relationship_keys(self, item_a, item_b) -> list:
        keys = []
        seen: set = set()
        for conn in item_a.connections:
            pair_match = (
                (conn.source_item == item_a and conn.target_item == item_b) or
                (conn.source_item == item_b and conn.target_item == item_a)
            )
            if not pair_match:
                continue
            rel_key = self._relationship_key(conn)
            if rel_key in seen:
                continue
            seen.add(rel_key)
            keys.append(rel_key)
        keys.sort()
        return keys

    def _get_pair_slot_offset(self, item_a, item_b, spacing: float = 16.0) -> float:
        rel_key = self._relationship_key()
        keys = self._get_pair_relationship_keys(item_a, item_b)
        if rel_key not in keys:
            keys.append(rel_key)
            keys.sort()
        if len(keys) <= 1:
            return 0.0
        slot_index = keys.index(rel_key)
        return (slot_index - ((len(keys) - 1) / 2.0)) * spacing

    def _get_direct_vertical_points(self, s_rect, t_rect):
        inner_padding = 2
        src_item = self.connection_item.source_item
        tgt_item = self.connection_item.target_item
        slot_offset = self._get_pair_slot_offset(src_item, tgt_item)

        if s_rect.bottom() <= t_rect.top():
            return self._direct_vertical_pair(s_rect, t_rect, inner_padding, slot_offset, "bottom", "top")
        if t_rect.bottom() <= s_rect.top():
            return self._direct_vertical_pair(s_rect, t_rect, inner_padding, slot_offset, "top", "bottom")
        return None

    def _direct_vertical_pair(self, s_rect, t_rect, inner_padding, slot_offset, s_side, t_side):
        overlap_left = max(s_rect.left() + inner_padding, t_rect.left() + inner_padding)
        overlap_right = min(s_rect.right() - inner_padding, t_rect.right() - inner_padding)
        if overlap_left > overlap_right:
            return None
        x = (overlap_left + overlap_right) / 2 + slot_offset
        x = max(overlap_left, min(overlap_right, x))
        src_item = self.connection_item.source_item
        tgt_item = self.connection_item.target_item
        start = self._get_anchor_with_slot(src_item, tgt_item, s_side)
        end = self._get_anchor_with_slot(tgt_item, src_item, t_side)
        start.setX(x)
        end.setX(x)
        return [start, end], s_side, t_side

    def _score_candidate(self, points: list, s_side: str, t_side: str) -> float:
        cost = sum((points[i] - points[i + 1]).manhattanLength() for i in range(len(points) - 1))
        cost += max(0, len(points) - 2) * 200
        preferred_s = self._preferred_side(self.connection_item.source_item, self.connection_item.target_item)
        preferred_t = self._preferred_side(self.connection_item.target_item, self.connection_item.source_item)
        if s_side != preferred_s:
            cost += 140
        if t_side != preferred_t:
            cost += 140
        if s_side == t_side:
            cost += 350
        if len(points) == 2 and cost < 100000:
            cost -= 100
        return cost

    def _try_candidate_pair(self, s_side: str, t_side: str, t_rect):
        src_item = self.connection_item.source_item
        tgt_item = self.connection_item.target_item
        start = self._get_anchor_with_slot(src_item, tgt_item, s_side)
        end = self._get_anchor_with_slot(tgt_item, src_item, t_side)
        tolerance = 25
        if s_side in ["left", "right"]:
            if abs(start.y() - end.y()) < tolerance:
                if t_rect.top() + 10 < start.y() < t_rect.bottom() - 10:
                    end.setY(start.y())
        elif s_side in ["top", "bottom"]:
            if abs(start.x() - end.x()) < tolerance:
                if t_rect.left() + 10 < start.x() < t_rect.right() - 10:
                    end.setX(start.x())
        points = self._get_pretty_manhattan_path(start, end, s_side, t_side)
        if points is None:
            router = (
                self.connection_item.scene().get_router()
                if hasattr(self.connection_item.scene(), 'get_router')
                else None
            )
            points = router.find_path(start, s_side, end, t_side) if router else [start, end]
        return points

    def _find_best_side_pair(self, t_rect):
        candidate_groups = [
            [("right", "left"), ("left", "right"), ("bottom", "top"), ("top", "bottom")],
            [("right", "right"), ("left", "left"), ("top", "top"), ("bottom", "bottom")],
        ]
        min_cost = float('inf')
        best_points = best_s_side = best_t_side = None
        for candidates in candidate_groups:
            for s_side, t_side in candidates:
                points = self._try_candidate_pair(s_side, t_side, t_rect)
                cost = self._score_candidate(points, s_side, t_side)
                if cost < min_cost:
                    min_cost = cost
                    best_points, best_s_side, best_t_side = points, s_side, t_side
            if best_points:
                break
        return best_points, best_s_side, best_t_side

    def _clamp_middle_points(self, points: list) -> list:
        if len(points) <= 2:
            return points
        margin = 15
        start_pt, end_pt = points[0], points[-1]
        min_x = min(start_pt.x(), end_pt.x()) - margin
        max_x = max(start_pt.x(), end_pt.x()) + margin
        min_y = min(start_pt.y(), end_pt.y()) - margin
        max_y = max(start_pt.y(), end_pt.y()) + margin
        for i in range(1, len(points) - 1):
            pt = points[i]
            points[i] = QPointF(
                max(min_x, min(max_x, pt.x())),
                max(min_y, min(max_y, pt.y())),
            )
        return points

    def compute_best_path(self) -> tuple:
        s_rect = item_visual_scene_rect(self.connection_item.source_item)
        t_rect = item_visual_scene_rect(self.connection_item.target_item)

        if self._is_chen_connection():
            s_item = self.connection_item.source_item
            t_item = self.connection_item.target_item
            s_center = item_visual_scene_rect(s_item).center()
            t_center = item_visual_scene_rect(t_item).center()
            start = get_chen_boundary_anchor(s_item, t_center)
            end = get_chen_boundary_anchor(t_item, s_center)
            s_side = self._preferred_side(s_item, t_item)
            t_side = self._preferred_side(t_item, s_item)
            return [start, end], s_side, t_side

        best_points = best_s_side = best_t_side = None
        direct_result = self._get_direct_vertical_points(s_rect, t_rect)
        if direct_result:
            best_points, best_s_side, best_t_side = direct_result

        if not best_points:
            best_points, best_s_side, best_t_side = self._find_best_side_pair(t_rect)

        if best_points and best_s_side and best_t_side:
            best_points = self._orthogonalize_end_segments(best_points, best_s_side, best_t_side)

        if best_points:
            best_points = self._clamp_middle_points(best_points)
            best_points = self._force_manhattan(best_points)

        return best_points, best_s_side, best_t_side


# ---------------------------------------------------------------------------
# Module-level helpers (extracted from long methods above)
# ---------------------------------------------------------------------------

def _dedup_points(pts: list) -> list:
    """Remove consecutive duplicate / near-duplicate points from a path."""
    if not pts:
        return pts
    dedup = [pts[0]]
    for p in pts[1:]:
        if (p - dedup[-1]).manhattanLength() >= 0.5:
            dedup.append(p)
    return dedup


def _side_stub(pt: QPointF, side: str, dist: float) -> QPointF:
    """Return a tiny stub point projecting outward from *pt* on *side*."""
    if side == "left":
        return QPointF(pt.x() - dist, pt.y())
    if side == "right":
        return QPointF(pt.x() + dist, pt.y())
    if side == "top":
        return QPointF(pt.x(), pt.y() - dist)
    return QPointF(pt.x(), pt.y() + dist)


def _fix_source_hinge(expanded: list, s_side: str, source_stub: QPointF) -> list:
    """Force the first interior hinge to align with the source stub direction."""
    if len(expanded) >= 3:
        s_next = expanded[2]
        if s_side in ("left", "right"):
            expanded[2] = QPointF(s_next.x(), source_stub.y())
        else:
            expanded[2] = QPointF(source_stub.x(), s_next.y())
    return expanded


def _fix_target_hinge(expanded: list, t_side: str, target_stub: QPointF, s_side: str, source_stub: QPointF) -> list:
    """Force the last interior hinge to align with the target stub direction."""
    if len(expanded) < 3:
        return expanded
    t_prev_idx = len(expanded) - 3
    t_prev = expanded[t_prev_idx]
    if t_prev_idx == 2 and len(expanded) == 5:
        if s_side in ("left", "right"):
            first_hinge = QPointF(t_prev.x(), source_stub.y())
            second_hinge = QPointF(t_prev.x(), target_stub.y())
        else:
            first_hinge = QPointF(source_stub.x(), t_prev.y())
            second_hinge = QPointF(target_stub.x(), t_prev.y())
        expanded[2] = first_hinge
        expanded.insert(3, second_hinge)
    else:
        if t_side in ("left", "right"):
            expanded[t_prev_idx] = QPointF(t_prev.x(), target_stub.y())
        else:
            expanded[t_prev_idx] = QPointF(target_stub.x(), t_prev.y())
    return expanded


def _build_path_candidates(start: QPointF, end: QPointF, s_side: str, t_side: str) -> list:
    """Build ordered list of candidate elbow paths for given side pair."""
    candidates = []
    side_gap = 24.0
    if t_side == "left":
        tx = end.x() - side_gap
        candidates.append([start, QPointF(tx, start.y()), QPointF(tx, end.y()), end])
    elif t_side == "right":
        tx = end.x() + side_gap
        candidates.append([start, QPointF(tx, start.y()), QPointF(tx, end.y()), end])
    elif t_side == "top":
        ty = end.y() - side_gap
        candidates.append([start, QPointF(start.x(), ty), QPointF(end.x(), ty), end])
    elif t_side == "bottom":
        ty = end.y() + side_gap
        candidates.append([start, QPointF(start.x(), ty), QPointF(end.x(), ty), end])
    if abs(start.x() - end.x()) < 0.5 or abs(start.y() - end.y()) < 0.5:
        candidates.append([start, end])
    candidates.append([start, QPointF(end.x(), start.y()), end])
    candidates.append([start, QPointF(start.x(), end.y()), end])
    return candidates
