from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from models import RoutePlan


def save_route(plan: RoutePlan, filepath: str) -> None:
    data = plan.to_dict()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_route(filepath: str) -> Optional[RoutePlan]:
    p = Path(filepath)
    if not p.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return RoutePlan.from_dict(data)
