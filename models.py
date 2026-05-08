from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Waypoint:
    lon: float
    lat: float
    index: int = 0

    def to_dict(self) -> dict:
        return {"lon": self.lon, "lat": self.lat, "index": self.index}

    @classmethod
    def from_dict(cls, d: dict) -> "Waypoint":
        return cls(lon=d["lon"], lat=d["lat"], index=d.get("index", 0))


@dataclass
class NoFlyZone:
    name: str
    reason: str
    points: List[List[float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "reason": self.reason, "points": self.points}

    @classmethod
    def from_dict(cls, d: dict) -> "NoFlyZone":
        return cls(name=d["name"], reason=d["reason"], points=d["points"])


@dataclass
class AltitudeZone:
    name: str
    altitude_limit: float
    points: List[List[float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "altitude_limit": self.altitude_limit,
            "points": self.points,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AltitudeZone":
        return cls(
            name=d["name"],
            altitude_limit=d["altitude_limit"],
            points=d["points"],
        )


@dataclass
class RoutePlan:
    waypoints: List[Waypoint] = field(default_factory=list)
    no_fly_zones: List[NoFlyZone] = field(default_factory=list)
    altitude_zones: List[AltitudeZone] = field(default_factory=list)
    speed_mps: float = 10.0
    battery_mah: float = 5000.0
    voltage: float = 14.8
    power_w: float = 200.0

    def to_dict(self) -> dict:
        return {
            "waypoints": [w.to_dict() for w in self.waypoints],
            "no_fly_zones": [z.to_dict() for z in self.no_fly_zones],
            "altitude_zones": [z.to_dict() for z in self.altitude_zones],
            "speed_mps": self.speed_mps,
            "battery_mah": self.battery_mah,
            "voltage": self.voltage,
            "power_w": self.power_w,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RoutePlan":
        return cls(
            waypoints=[Waypoint.from_dict(w) for w in d.get("waypoints", [])],
            no_fly_zones=[NoFlyZone.from_dict(z) for z in d.get("no_fly_zones", [])],
            altitude_zones=[
                AltitudeZone.from_dict(z) for z in d.get("altitude_zones", [])
            ],
            speed_mps=d.get("speed_mps", 10.0),
            battery_mah=d.get("battery_mah", 5000.0),
            voltage=d.get("voltage", 14.8),
            power_w=d.get("power_w", 200.0),
        )


NO_FLY_ZONE_REASONS = ["机场", "军事区", "政府机关", "人口密集区"]


def get_default_no_fly_zones() -> List[NoFlyZone]:
    return [
        NoFlyZone(
            name="首都国际机场禁飞区",
            reason="机场",
            points=[
                [116.580, 40.080],
                [116.620, 40.080],
                [116.620, 40.050],
                [116.580, 40.050],
            ],
        ),
        NoFlyZone(
            name="某军事基地禁飞区",
            reason="军事区",
            points=[
                [116.350, 39.980],
                [116.390, 39.980],
                [116.390, 39.955],
                [116.370, 39.940],
                [116.350, 39.955],
            ],
        ),
        NoFlyZone(
            name="中南海政府机关禁飞区",
            reason="政府机关",
            points=[
                [116.370, 39.920],
                [116.395, 39.920],
                [116.395, 39.905],
                [116.370, 39.905],
            ],
        ),
    ]


def get_default_altitude_zones() -> List[AltitudeZone]:
    return [
        AltitudeZone(
            name="CBD限高区",
            altitude_limit=120.0,
            points=[
                [116.440, 39.925],
                [116.475, 39.925],
                [116.475, 39.900],
                [116.440, 39.900],
            ],
        ),
    ]
