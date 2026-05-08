from __future__ import annotations

import math
from typing import List, Tuple


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def point_in_polygon(px: float, py: float, polygon: List[List[float]]) -> bool:
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def _ccw(
    ax: float, ay: float, bx: float, by: float, cx: float, cy: float
) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def segments_intersect(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    p4: Tuple[float, float],
) -> bool:
    d1 = _ccw(p3[0], p3[1], p4[0], p4[1], p1[0], p1[1])
    d2 = _ccw(p3[0], p3[1], p4[0], p4[1], p2[0], p2[1])
    d3 = _ccw(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])
    d4 = _ccw(p1[0], p1[1], p2[0], p2[1], p4[0], p4[1])
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
        (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
    ):
        return True
    if d1 == 0 and _on_segment(p3, p4, p1):
        return True
    if d2 == 0 and _on_segment(p3, p4, p2):
        return True
    if d3 == 0 and _on_segment(p1, p2, p3):
        return True
    if d4 == 0 and _on_segment(p1, p2, p4):
        return True
    return False


def _on_segment(
    p: Tuple[float, float],
    q: Tuple[float, float],
    r: Tuple[float, float],
) -> bool:
    if (
        min(p[0], q[0]) <= r[0] <= max(p[0], q[0])
        and min(p[1], q[1]) <= r[1] <= max(p[1], q[1])
    ):
        return True
    return False


def line_intersects_polygon(
    p1: Tuple[float, float], p2: Tuple[float, float], polygon: List[List[float]]
) -> bool:
    n = len(polygon)
    if n < 3:
        return False
    for i in range(n):
        p3 = (polygon[i][0], polygon[i][1])
        p4 = (polygon[(i + 1) % n][0], polygon[(i + 1) % n][1])
        if segments_intersect(p1, p2, p3, p4):
            return True
    if point_in_polygon(p1[0], p1[1], polygon):
        return True
    if point_in_polygon(p2[0], p2[1], polygon):
        return True
    return False
