"""Load per transformer for the control center (US-19, T-19.1).

    load_kw      = delivered kWh in the 15-minute interval x 4   (average power in the interval)
    capacity_pct = load_kw / capacity_kva x 100                  (unit power factor, as the brief assumes)

Delivered energy comes from F5; capacity comes from F4.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import Depends

from app.api.control_center.f5_client import F5Client, get_f5_client
from app.api.control_center.repository import ControlCenterRepository, TransformerInfo, get_repository
from app.core.errors import NotFoundError

MAX_RANGE = timedelta(days=7)
INTERVALS_PER_HOUR = 4
KW = Decimal("0.01")
PCT = Decimal("0.1")


class InvalidRange(Exception):
    """end before start, empty range, or a range above 7 days."""


def to_point(interval_start: datetime, delivered_kwh: float, capacity_kva: Decimal) -> dict:
    load_kw = Decimal(str(delivered_kwh)) * INTERVALS_PER_HOUR
    return {
        "interval_start": interval_start,
        "load_kw": load_kw.quantize(KW),
        "capacity_pct": (load_kw / capacity_kva * 100).quantize(PCT),
    }


class ControlCenterService:
    def __init__(self, repo: ControlCenterRepository, f5: F5Client):
        self.repo = repo
        self.f5 = f5

    def _transformer(self, code: str) -> TransformerInfo:
        info = self.repo.get_transformer(code)
        if info is None:
            raise NotFoundError("Transformer", code)
        return info

    def load(self, code: str, start: datetime, end: datetime) -> dict:
        if end <= start:
            raise InvalidRange("end must be after start")
        if end - start > MAX_RANGE:
            raise InvalidRange("range must be 7 days or less")
        info = self._transformer(code)
        points = [to_point(ts, kwh, info.capacity_kva) for ts, kwh in self.f5.energy(code, start, end)]
        return {"transformer_code": code, "capacity_kva": info.capacity_kva, "interval_minutes": 15, "points": points}


def get_service(
    repo: ControlCenterRepository = Depends(get_repository),
    f5: F5Client = Depends(get_f5_client),
) -> ControlCenterService:
    return ControlCenterService(repo, f5)
