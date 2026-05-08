from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from geometry import haversine, line_intersects_polygon
from models import NoFlyZone, AltitudeZone, Waypoint


@dataclass
class SegmentResult:
    index: int
    from_wp: Waypoint
    to_wp: Waypoint
    distance_km: float
    conflicts: List[str] = field(default_factory=list)
    altitude_limits: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    total_distance_km: float = 0.0
    flight_time_min: float = 0.0
    battery_time_min: float = 0.0
    battery_sufficient: bool = True
    segments: List[SegmentResult] = field(default_factory=list)
    conflict_segments: List[int] = field(default_factory=list)
    passed: bool = True
    warnings: List[str] = field(default_factory=list)


def analyze_route(
    waypoints: List[Waypoint],
    no_fly_zones: List[NoFlyZone],
    altitude_zones: List[AltitudeZone],
    speed_mps: float = 10.0,
    battery_mah: float = 5000.0,
    voltage: float = 14.8,
    power_w: float = 200.0,
) -> AnalysisResult:
    result = AnalysisResult()

    if len(waypoints) < 2:
        result.warnings.append("至少需要2个航点才能规划航线")
        return result

    total_dist = 0.0
    for i in range(len(waypoints) - 1):
        wp1 = waypoints[i]
        wp2 = waypoints[i + 1]
        seg_dist = haversine(wp1.lon, wp1.lat, wp2.lon, wp2.lat)

        seg = SegmentResult(
            index=i,
            from_wp=wp1,
            to_wp=wp2,
            distance_km=seg_dist,
        )

        p1 = (wp1.lon, wp1.lat)
        p2 = (wp2.lon, wp2.lat)

        for zone in no_fly_zones:
            if line_intersects_polygon(p1, p2, zone.points):
                seg.conflicts.append(f"{zone.name}({zone.reason})")

        for zone in altitude_zones:
            if line_intersects_polygon(p1, p2, zone.points):
                seg.altitude_limits.append(f"{zone.name}(限高{zone.altitude_limit:.0f}m)")

        if seg.conflicts:
            result.conflict_segments.append(i)
            result.passed = False

        total_dist += seg_dist
        result.segments.append(seg)

    result.total_distance_km = total_dist
    result.flight_time_min = (total_dist / max(speed_mps, 0.1)) * 60.0 / 60.0

    battery_wh = (battery_mah / 1000.0) * voltage
    battery_hours = battery_wh / max(power_w, 0.1)
    result.battery_time_min = battery_hours * 60.0
    result.battery_sufficient = result.flight_time_min <= result.battery_time_min

    if not result.battery_sufficient:
        result.passed = False
        result.warnings.append(
            f"电池续航不足: 需飞{result.flight_time_min:.1f}分钟, "
            f"可用{result.battery_time_min:.1f}分钟"
        )

    if result.conflict_segments:
        zone_names = set()
        for si in result.conflict_segments:
            for c in result.segments[si].conflicts:
                zone_names.add(c)
        result.warnings.append(f"航线经过禁飞区: {', '.join(zone_names)}")

    for seg in result.segments:
        if seg.altitude_limits:
            result.warnings.append(
                f"航段{seg.index}经过限高区: {', '.join(seg.altitude_limits)}"
            )

    return result
