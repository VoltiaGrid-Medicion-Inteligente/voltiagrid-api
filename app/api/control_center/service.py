"""Load per transformer and overload alerts for the control center (US-19, T-19.1 and T-19.2).

    load_kw      = delivered kWh in the 15-minute interval x 4   (average power in the interval)
    capacity_pct = load_kw / capacity_kva x 100                  (unit power factor, as the brief assumes)

Delivered energy comes from F5; capacity comes from F4. A transformer is
overloaded when capacity_pct is above 100 in the interval checked.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import Depends

from app.api.control_center.f5_client import F5Client, get_f5_client
from app.api.control_center.repository import ControlCenterRepository, TransformerInfo, get_repository
from app.core.errors import NotFoundError


MAX_RANGE = timedelta(days=7)
STEP = timedelta(minutes=15)
OVERLOAD_PCT = Decimal("100")
INTERVALS_PER_HOUR = 4
KW = Decimal("0.01")


class InvalidRange(Exception):
    """end before start, empty range, or a range above 7 days."""



def interval_containing(ts: datetime) -> datetime:
    """Start of the 15-minute interval that contains ts."""
    return ts.replace(minute=ts.minute - ts.minute % 15, second=0, microsecond=0)


def to_point(interval_start: datetime, delivered_kwh: float, capacity_kva: Decimal) -> dict:
    load_kw = Decimal(str(delivered_kwh)) * INTERVALS_PER_HOUR
    capacity_pct = load_kw / capacity_kva * 100
    return {
        "interval_start": interval_start,
        "load_kw": load_kw.quantize(KW),
        "capacity_pct": capacity_pct.quantize(Decimal("0.1")),
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

    def overload_alerts(self, at: datetime, circuit_code: str | None = None) -> list[dict]:
        """Transformers above 100% of their capacity in the 15-minute interval that contains `at`."""
        interval = interval_containing(at)
        alerts = []
        for info in self.repo.list_transformers(circuit_code):
            try:
                readings = self.f5.energy(info.code, interval, interval + STEP)
            except NotFoundError:
                continue  # in F4 but feeds no meter yet: no load, no alert
            for ts, kwh in readings:
                point = to_point(ts, kwh, info.capacity_kva)
                if point["capacity_pct"] > OVERLOAD_PCT:
                    alerts.append({"transformer_code": info.code, "circuit_code": info.circuit_code,
                                   "capacity_kva": info.capacity_kva, **point})
        return sorted(alerts, key=lambda a: a["capacity_pct"], reverse=True)


def get_service(
    repo: ControlCenterRepository = Depends(get_repository),
    f5: F5Client = Depends(get_f5_client),
) -> ControlCenterService:
    return ControlCenterService(repo, f5)
