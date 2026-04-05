import heapq
# from PyQt6.QtCore import QPointF, QRectF
from PySide6.QtCore import QPointF, QRectF
from widgets.erd.items.table_item import ERDTableItem

class ERDRouter:
    def __init__(self, scene_rect: QRectF, obstacles: list[QRectF], grid_size=20):
        self.grid_size = grid_size
        self.min_x = int(scene_rect.left() // grid_size)
        self.max_x = int(scene_rect.right() // grid_size)
        self.min_y = int(scene_rect.top() // grid_size)
        self.max_y = int(scene_rect.bottom() // grid_size)
        
        self.blocked = set()
        for obs in obstacles:
            ox_start = int((obs.left() - grid_size/2) // grid_size)
            ox_end = int((obs.right() + grid_size/2) // grid_size)
            oy_start = int((obs.top() - grid_size/2) // grid_size)
            oy_end = int((obs.bottom() + grid_size/2) // grid_size)
            
            for x in range(ox_start, ox_end + 1):
                for y in range(oy_start, oy_end + 1):
                    self.blocked.add((x, y))

    def _to_grid(self, pt: QPointF):
        return (int(pt.x() // self.grid_size), int(pt.y() // self.grid_size))
        
    def _from_grid(self, gx, gy):
        return QPointF(gx * self.grid_size, gy * self.grid_size)

    def find_path(self, start: QPointF, start_side: str, end: QPointF, end_side: str) -> list[QPointF]:
        def get_stub(pt, side, dist=2):
            gx, gy = self._to_grid(pt)
            if side == "left": return (gx - dist, gy)
            if side == "right": return (gx + dist, gy)
            if side == "top": return (gx, gy - dist)
            if side == "bottom": return (gx, gy + dist)
            return (gx, gy)
            
        start_grid = self._to_grid(start)
        end_grid = self._to_grid(end)
        
        stub_start = get_stub(start, start_side, 2)
        stub_end = get_stub(end, end_side, 2)
        
        safe_blocked = self.blocked.copy()
        for pt in [start_grid, stub_start, stub_end, end_grid]:
            if pt in safe_blocked:
                safe_blocked.remove(pt)
                
        def heuristic(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])
            
        queue = [(0, stub_start, [stub_start])]
        visited = {stub_start: 0}
        
        best_path = None
        iter_count = 0
        
        while queue and iter_count < 1500: # Limit iterations to prevent UI freeze
            iter_count += 1
            cost, current, path = heapq.heappop(queue)
            
            if current == stub_end:
                best_path = path
                break
                
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nxt = (current[0] + dx, current[1] + dy)
                
                if nxt[0] < self.min_x or nxt[0] > self.max_x or nxt[1] < self.min_y or nxt[1] > self.max_y:
                    continue
                    
                if nxt in safe_blocked and nxt != stub_end:
                    continue
                    
                new_cost = cost + 1
                
                if len(path) > 1:
                    prev = path[-2]
                    # Penalize turns
                    if (nxt[0] - current[0] != current[0] - prev[0]) or (nxt[1] - current[1] != current[1] - prev[1]):
                        new_cost += 5
                        
                if nxt not in visited or new_cost < visited[nxt]:
                    visited[nxt] = new_cost
                    priority = new_cost + heuristic(nxt, stub_end)
                    heapq.heappush(queue, (priority, nxt, path + [nxt]))
                    
        res = [start]
        if best_path:
            for pt in best_path:
                res.append(self._from_grid(pt[0], pt[1]))
        else:
            # Fallback direct path
            res.append(self._from_grid(stub_start[0], stub_start[1]))
            res.append(self._from_grid(stub_end[0], stub_end[1]))
            
        res.append(end)
        
        # Deduplication and Collinear consolidation
        if len(res) > 2:
            final = [res[0]]
            for i in range(1, len(res)):
                p = res[i]
                prev = final[-1]
                if (p - prev).manhattanLength() < 0.5: continue
                
                if len(final) >= 2:
                    p_prev = final[-2]
                    is_h = abs(p_prev.y() - prev.y()) < 0.1 and abs(prev.y() - p.y()) < 0.1
                    is_v = abs(p_prev.x() - prev.x()) < 0.1 and abs(prev.x() - p.x()) < 0.1
                    if is_h or is_v:
                        final[-1] = p
                        continue
                final.append(p)
            res = final
            
        return res


class ERDConnectionPathPlanner:
    def __init__(self, connection_item):
        self.connection_item = connection_item

    def _relationship_key(self, conn=None):
        relation_conn = conn or self.connection_item
        return (
            relation_conn.source_item.table_name,
            relation_conn.source_col,
            relation_conn.target_item.table_name,
            relation_conn.target_col,
        )

    def _preferred_side(self, item, other_item):
        item_rect = item.sceneBoundingRect()
        other_rect = other_item.sceneBoundingRect()

        dx = other_rect.center().x() - item_rect.center().x()
        dy = other_rect.center().y() - item_rect.center().y()

        if abs(dx) >= abs(dy):
            return "right" if dx >= 0 else "left"
        return "bottom" if dy >= 0 else "top"

    def _get_side_relationship_keys(self, item, side):
        keys = []
        seen = set()

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

    def _apply_slot_offset(self, item, side, anchor):
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

        rect = item.sceneBoundingRect()
        margin = 12.0

        if side in ("left", "right"):
            y = max(rect.top() + margin, min(rect.bottom() - margin, anchor.y() + offset))
            return QPointF(anchor.x(), y)

        x = max(rect.left() + margin, min(rect.right() - margin, anchor.x() + offset))
        return QPointF(x, anchor.y())

    def _get_base_anchor(self, item, side):
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

    def _get_anchor_with_slot(self, item, other_item, side):
        anchor = self._get_base_anchor(item, side)
        return self._apply_slot_offset(item, side, anchor)

    def _orthogonalize_end_segments(self, points, s_side, t_side):
        if not points or len(points) < 2:
            return points

        pts = list(points)
        stub_px = 2.0

        p0 = pts[0]
        pn = pts[-1]

        if s_side == "left":
            source_stub = QPointF(p0.x() - stub_px, p0.y())
        elif s_side == "right":
            source_stub = QPointF(p0.x() + stub_px, p0.y())
        elif s_side == "top":
            source_stub = QPointF(p0.x(), p0.y() - stub_px)
        else:
            source_stub = QPointF(p0.x(), p0.y() + stub_px)

        if t_side == "left":
            target_stub = QPointF(pn.x() - stub_px, pn.y())
        elif t_side == "right":
            target_stub = QPointF(pn.x() + stub_px, pn.y())
        elif t_side == "top":
            target_stub = QPointF(pn.x(), pn.y() - stub_px)
        else:
            target_stub = QPointF(pn.x(), pn.y() + stub_px)

        if len(pts) == 2:
            expanded = [p0, source_stub, target_stub, pn]
            dedup = [expanded[0]]
            for point in expanded[1:]:
                if (point - dedup[-1]).manhattanLength() >= 0.5:
                    dedup.append(point)
            return dedup

        middle = pts[1:-1]
        expanded = [p0, source_stub] + middle + [target_stub, pn]

        if len(expanded) >= 3:
            s_next = expanded[2]
            if s_side in ("left", "right"):
                expanded[2] = QPointF(s_next.x(), source_stub.y())
            else:
                expanded[2] = QPointF(source_stub.x(), s_next.y())

        if len(expanded) >= 3:
            t_prev_idx = len(expanded) - 3
            t_prev = expanded[t_prev_idx]
            # When there is only one middle hinge, avoid overwriting the same point twice.
            # Insert an extra hinge so both source and target stubs remain orthogonal.
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

        dedup = [expanded[0]]
        for point in expanded[1:]:
            if (point - dedup[-1]).manhattanLength() >= 0.5:
                dedup.append(point)

        return dedup

    def _force_manhattan(self, points):
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

        dedup = [normalized[0]]
        for point in normalized[1:]:
            if (point - dedup[-1]).manhattanLength() >= 0.5:
                dedup.append(point)

        return dedup

    def _is_source_direction_valid(self, start, nxt, side):
        eps = 0.5
        if side == "left":
            return nxt.x() <= start.x() - eps
        if side == "right":
            return nxt.x() >= start.x() + eps
        if side == "top":
            return nxt.y() <= start.y() - eps
        return nxt.y() >= start.y() + eps

    def _is_target_direction_valid(self, prev, end, side):
        eps = 0.5
        if side == "left":
            return prev.x() <= end.x() - eps
        if side == "right":
            return prev.x() >= end.x() + eps
        if side == "top":
            return prev.y() <= end.y() - eps
        return prev.y() >= end.y() + eps

    def _segment_hits_rect(self, p1, p2, rect):
        eps = 0.5

        if abs(p1.x() - p2.x()) < eps:
            x = p1.x()
            if rect.left() + eps < x < rect.right() - eps:
                y1 = min(p1.y(), p2.y())
                y2 = max(p1.y(), p2.y())
                return y2 > rect.top() + eps and y1 < rect.bottom() - eps
            return False

        if abs(p1.y() - p2.y()) < eps:
            y = p1.y()
            if rect.top() + eps < y < rect.bottom() - eps:
                x1 = min(p1.x(), p2.x())
                x2 = max(p1.x(), p2.x())
                return x2 > rect.left() + eps and x1 < rect.right() - eps
            return False

        return False

    def _path_hits_obstacles(self, points):
        scene = self.connection_item.scene()
        if not scene:
            return False

        for item in scene.items():
            if not isinstance(item, ERDTableItem):
                continue
            if item == self.connection_item.source_item or item == self.connection_item.target_item:
                continue

            rect = item.sceneBoundingRect().adjusted(2, 2, -2, -2)
            for i in range(len(points) - 1):
                if self._segment_hits_rect(points[i], points[i + 1], rect):
                    return True

        return False

    def _get_pretty_manhattan_path(self, start, end, s_side, t_side):
        candidates = []

        # Prefer side-aware elbow paths so the final segment approaches the
        # target from its declared side without forcing a distant dogleg.
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

    def _get_pair_relationship_keys(self, item_a, item_b):
        keys = []
        seen = set()

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

    def _get_pair_slot_offset(self, item_a, item_b, spacing=16.0):
        rel_key = self._relationship_key()
        keys = self._get_pair_relationship_keys(item_a, item_b)
        if rel_key not in keys:
            keys.append(rel_key)
            keys.sort()

        if len(keys) <= 1:
            return 0.0

        slot_index = keys.index(rel_key)
        centered_index = slot_index - ((len(keys) - 1) / 2.0)
        return centered_index * spacing

    def _get_direct_vertical_points(self, s_rect, t_rect):
        inner_padding = 2

        if s_rect.bottom() <= t_rect.top():
            overlap_left = max(s_rect.left() + inner_padding, t_rect.left() + inner_padding)
            overlap_right = min(s_rect.right() - inner_padding, t_rect.right() - inner_padding)
            if overlap_left <= overlap_right:
                x = (overlap_left + overlap_right) / 2
                x += self._get_pair_slot_offset(self.connection_item.source_item, self.connection_item.target_item)
                x = max(overlap_left, min(overlap_right, x))
                start = self._get_anchor_with_slot(self.connection_item.source_item, self.connection_item.target_item, "bottom")
                end = self._get_anchor_with_slot(self.connection_item.target_item, self.connection_item.source_item, "top")
                start.setX(x)
                end.setX(x)
                return [start, end], "bottom", "top"

        if t_rect.bottom() <= s_rect.top():
            overlap_left = max(s_rect.left() + inner_padding, t_rect.left() + inner_padding)
            overlap_right = min(s_rect.right() - inner_padding, t_rect.right() - inner_padding)
            if overlap_left <= overlap_right:
                x = (overlap_left + overlap_right) / 2
                x += self._get_pair_slot_offset(self.connection_item.source_item, self.connection_item.target_item)
                x = max(overlap_left, min(overlap_right, x))
                start = self._get_anchor_with_slot(self.connection_item.source_item, self.connection_item.target_item, "top")
                end = self._get_anchor_with_slot(self.connection_item.target_item, self.connection_item.source_item, "bottom")
                start.setX(x)
                end.setX(x)
                return [start, end], "top", "bottom"

        return None

    def compute_best_path(self):
        s_rect = self.connection_item.source_item.sceneBoundingRect()
        t_rect = self.connection_item.target_item.sceneBoundingRect()

        best_points = None
        best_s_side = None
        best_t_side = None

        direct_result = self._get_direct_vertical_points(s_rect, t_rect)
        if direct_result:
            best_points, best_s_side, best_t_side = direct_result

        if not best_points:
            candidate_groups = [
                [
                    ("right", "left"),
                    ("left", "right"),
                    ("bottom", "top"),
                    ("top", "bottom"),
                ],
                [
                    ("right", "right"),
                    ("left", "left"),
                    ("top", "top"),
                    ("bottom", "bottom"),
                ],
            ]

            min_cost = float('inf')

            for candidates in candidate_groups:
                for s_side, t_side in candidates:
                    start = self._get_anchor_with_slot(self.connection_item.source_item, self.connection_item.target_item, s_side)
                    end = self._get_anchor_with_slot(self.connection_item.target_item, self.connection_item.source_item, t_side)

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
                        router = self.connection_item.scene().get_router() if hasattr(self.connection_item.scene(), 'get_router') else None
                        if router:
                            points = router.find_path(start, s_side, end, t_side)
                        else:
                            points = [start, end]

                    cost = 0
                    for i in range(len(points) - 1):
                        cost += (points[i] - points[i + 1]).manhattanLength()
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

                    if cost < min_cost:
                        min_cost = cost
                        best_points = points
                        best_s_side = s_side
                        best_t_side = t_side

                if best_points:
                    break

        if best_points and best_s_side and best_t_side:
            best_points = self._orthogonalize_end_segments(best_points, best_s_side, best_t_side)

        if best_points and len(best_points) > 2:
            margin = 15
            start_pt = best_points[0]
            end_pt = best_points[-1]
            min_x = min(start_pt.x(), end_pt.x()) - margin
            max_x = max(start_pt.x(), end_pt.x()) + margin
            min_y = min(start_pt.y(), end_pt.y()) - margin
            max_y = max(start_pt.y(), end_pt.y()) + margin

            for i in range(1, len(best_points) - 1):
                pt = best_points[i]
                clamped_x = max(min_x, min(max_x, pt.x()))
                clamped_y = max(min_y, min(max_y, pt.y()))
                best_points[i] = QPointF(clamped_x, clamped_y)

        if best_points:
            best_points = self._force_manhattan(best_points)

        return best_points, best_s_side, best_t_side

def get_dynamic_anchor(item, side):
    rect = item.sceneBoundingRect()
    if side == "left" or side == "right":
        x = rect.left() if side == "left" else rect.right()
        return QPointF(x, rect.top() + rect.height() / 2)
    elif side == "top" or side == "bottom":
         y = rect.top() if side == "top" else rect.bottom()
         return QPointF(rect.left() + rect.width() / 2, y)
    return rect.center()
