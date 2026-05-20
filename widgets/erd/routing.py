import heapq
import math
# from PyQt6.QtCore import QPointF, QRectF
from PySide6.QtCore import QPointF, QRectF
from widgets.erd.items.table_item import ERDTableItem
from widgets.erd.items.resizable import item_visual_scene_rect


def get_chen_boundary_anchor(item, target_point):
    """Compute where a line from item's center to target_point exits the item's
    actual visual boundary (ellipse, rectangle, or diamond)."""
    from widgets.erd.items.attribute_item import ERDAttributeItem
    from widgets.erd.items.relationship_diamond_item import ERDRelationshipDiamondItem
    from widgets.erd.items.resizable import item_visual_scene_rect

    rect = item_visual_scene_rect(item)
    cx, cy = rect.center().x(), rect.center().y()
    dx = target_point.x() - cx
    dy = target_point.y() - cy

    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return QPointF(cx, cy)

    half_w = rect.width() / 2
    half_h = rect.height() / 2

    if isinstance(item, ERDAttributeItem):
        # Ellipse: parametric intersection
        # Line: (cx + t*dx, cy + t*dy) intersects ellipse (x-cx)²/a² + (y-cy)²/b² = 1
        # t = 1 / sqrt((dx/a)² + (dy/b)²)
        if half_w < 1e-6 or half_h < 1e-6:
            return QPointF(cx, cy)
        t = 1.0 / math.sqrt((dx / half_w) ** 2 + (dy / half_h) ** 2)
        return QPointF(cx + t * dx, cy + t * dy)

    if isinstance(item, ERDRelationshipDiamondItem):
        # Diamond with vertices at (cx, cy-half_h), (cx+half_w, cy), (cx, cy+half_h), (cx-half_w, cy)
        # Edge equation: |x-cx|/half_w + |y-cy|/half_h = 1
        # For ray from center: t * (|dx|/half_w + |dy|/half_h) = 1
        denom = abs(dx) / half_w + abs(dy) / half_h
        if denom < 1e-6:
            return QPointF(cx, cy)
        t = 1.0 / denom
        return QPointF(cx + t * dx, cy + t * dy)

    # Rectangle (Entity, Weak Entity, fallback)
    # Find which edge the ray hits first
    if abs(dx) * half_h > abs(dy) * half_w:
        # Hits left or right edge
        t = half_w / abs(dx)
    else:
        # Hits top or bottom edge
        t = half_h / abs(dy)
    return QPointF(cx + t * dx, cy + t * dy)

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
            if side == "left":
                return (gx - dist, gy)
            if side == "right":
                return (gx + dist, gy)
            if side == "top":
                return (gx, gy - dist)
            if side == "bottom":
                return (gx, gy + dist)
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
                if (p - prev).manhattanLength() < 0.5:
                    continue
                
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


def get_dynamic_anchor(item, side: str) -> QPointF:
    rect = item_visual_scene_rect(item)
    if side in ("left", "right"):
        x = rect.left() if side == "left" else rect.right()
        return QPointF(x, rect.top() + rect.height() / 2)
    if side in ("top", "bottom"):
        y = rect.top() if side == "top" else rect.bottom()
        return QPointF(rect.left() + rect.width() / 2, y)
    return rect.center()
