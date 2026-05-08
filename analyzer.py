from typing import List

from models import (
    Waypoint,
    NoFlyZone,
    FlightPlan,
    BatteryConfig,
    SegmentInfo,
    AnalysisResult
)
from geometry import haversine_distance, segment_intersects_polygon


class FlightAnalyzer:
    def __init__(self):
        self.default_speed_kmh = 30.0

    def analyze(
        self,
        flight_plan: FlightPlan,
        battery_config: BatteryConfig,
        speed_kmh: float = None
    ) -> AnalysisResult:
        waypoints = flight_plan.waypoints
        no_fly_zones = flight_plan.no_fly_zones

        if len(waypoints) < 2:
            return self._empty_result(battery_config)

        speed = speed_kmh if speed_kmh else self.default_speed_kmh

        segments = []
        total_distance = 0.0
        conflicts = []

        for i in range(len(waypoints) - 1):
            start_wp = waypoints[i]
            end_wp = waypoints[i + 1]

            distance = haversine_distance(
                start_wp.latitude, start_wp.longitude,
                end_wp.latitude, end_wp.longitude
            )
            total_distance += distance

            segment = SegmentInfo(
                segment_index=i,
                start_waypoint=start_wp,
                end_waypoint=end_wp,
                distance_km=distance,
                cumulative_distance_km=total_distance
            )

            segment_geom = (
                (start_wp.longitude, start_wp.latitude),
                (end_wp.longitude, end_wp.latitude)
            )

            for zone in no_fly_zones:
                if segment_intersects_polygon(segment_geom, zone.points):
                    segment.has_conflict = True
                    segment.conflict_zone_id = zone.id
                    segment.conflict_zone_name = zone.name
                    conflicts.append(segment)
                    break

            segments.append(segment)

        estimated_time = (total_distance / speed) * 60 if speed > 0 else 0
        battery_available = battery_config.flight_time_minutes
        battery_sufficient = estimated_time <= battery_available

        return AnalysisResult(
            total_distance_km=total_distance,
            estimated_time_minutes=estimated_time,
            segments=segments,
            conflicts=conflicts,
            battery_sufficient=battery_sufficient,
            battery_required_minutes=estimated_time,
            battery_available_minutes=battery_available
        )

    def _empty_result(self, battery_config: BatteryConfig) -> AnalysisResult:
        return AnalysisResult(
            total_distance_km=0.0,
            estimated_time_minutes=0.0,
            segments=[],
            conflicts=[],
            battery_sufficient=True,
            battery_required_minutes=0.0,
            battery_available_minutes=battery_config.flight_time_minutes
        )
