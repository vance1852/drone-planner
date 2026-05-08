from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ZoneType(Enum):
    NO_FLY = "no_fly"
    RESTRICTED_ALTITUDE = "restricted_altitude"


class NoFlyReason(Enum):
    AIRPORT = "机场"
    MILITARY = "军事区"
    GOVERNMENT = "政府机关"
    DENSE_POPULATION = "人口密集区"


@dataclass
class Waypoint:
    id: int
    longitude: float
    latitude: float
    altitude: float = 50.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "longitude": self.longitude,
            "latitude": self.latitude,
            "altitude": self.altitude
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Waypoint':
        return cls(
            id=data["id"],
            longitude=data["longitude"],
            latitude=data["latitude"],
            altitude=data.get("altitude", 50.0)
        )


@dataclass
class NoFlyZone:
    id: int
    name: str
    reason: NoFlyReason
    points: List[tuple]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "reason": self.reason.value,
            "points": self.points
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NoFlyZone':
        return cls(
            id=data["id"],
            name=data["name"],
            reason=NoFlyReason(data["reason"]),
            points=[tuple(p) for p in data["points"]]
        )


@dataclass
class RestrictedAltitudeZone:
    id: int
    name: str
    max_altitude: float
    points: List[tuple]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "max_altitude": self.max_altitude,
            "points": self.points
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'RestrictedAltitudeZone':
        return cls(
            id=data["id"],
            name=data["name"],
            max_altitude=data["max_altitude"],
            points=[tuple(p) for p in data["points"]]
        )


@dataclass
class FlightPlan:
    waypoints: List[Waypoint] = field(default_factory=list)
    no_fly_zones: List[NoFlyZone] = field(default_factory=list)
    restricted_altitude_zones: List[RestrictedAltitudeZone] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "waypoints": [wp.to_dict() for wp in self.waypoints],
            "no_fly_zones": [nz.to_dict() for nz in self.no_fly_zones],
            "restricted_altitude_zones": [rz.to_dict() for rz in self.restricted_altitude_zones]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'FlightPlan':
        return cls(
            waypoints=[Waypoint.from_dict(wp) for wp in data.get("waypoints", [])],
            no_fly_zones=[NoFlyZone.from_dict(nz) for nz in data.get("no_fly_zones", [])],
            restricted_altitude_zones=[RestrictedAltitudeZone.from_dict(rz) for rz in data.get("restricted_altitude_zones", [])]
        )


@dataclass
class BatteryConfig:
    capacity_mah: float
    voltage: float
    power_w: float

    @property
    def total_energy_wh(self) -> float:
        return (self.capacity_mah / 1000) * self.voltage

    @property
    def flight_time_minutes(self) -> float:
        if self.power_w <= 0:
            return 0
        return (self.total_energy_wh / self.power_w) * 60


@dataclass
class SegmentInfo:
    segment_index: int
    start_waypoint: Waypoint
    end_waypoint: Waypoint
    distance_km: float
    cumulative_distance_km: float
    has_conflict: bool = False
    conflict_zone_id: Optional[int] = None
    conflict_zone_name: Optional[str] = None


@dataclass
class AnalysisResult:
    total_distance_km: float
    estimated_time_minutes: float
    segments: List[SegmentInfo]
    conflicts: List[SegmentInfo]
    battery_sufficient: bool
    battery_required_minutes: float
    battery_available_minutes: float

    @property
    def has_conflict(self) -> bool:
        return len(self.conflicts) > 0
