import json
from pathlib import Path
from typing import Optional

from models import (
    FlightPlan,
    NoFlyZone,
    RestrictedAltitudeZone,
    NoFlyReason
)


class FlightPlanPersistence:
    def save(self, flight_plan: FlightPlan, file_path: str) -> bool:
        try:
            data = flight_plan.to_dict()
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def load(self, file_path: str) -> Optional[FlightPlan]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return FlightPlan.from_dict(data)
        except Exception:
            return None


def get_default_no_fly_zones() -> list:
    return [
        NoFlyZone(
            id=1,
            name="首都国际机场",
            reason=NoFlyReason.AIRPORT,
            points=[
                (116.58, 40.06),
                (116.60, 40.06),
                (116.60, 40.08),
                (116.58, 40.08)
            ]
        ),
        NoFlyZone(
            id=2,
            name="某军事基地",
            reason=NoFlyReason.MILITARY,
            points=[
                (116.38, 39.90),
                (116.40, 39.89),
                (116.42, 39.91),
                (116.41, 39.94),
                (116.39, 39.93)
            ]
        ),
        NoFlyZone(
            id=3,
            name="中南海",
            reason=NoFlyReason.GOVERNMENT,
            points=[
                (116.37, 39.91),
                (116.39, 39.91),
                (116.39, 39.93),
                (116.37, 39.93)
            ]
        )
    ]


def get_default_flight_plan() -> FlightPlan:
    plan = FlightPlan()
    plan.no_fly_zones = get_default_no_fly_zones()
    return plan
