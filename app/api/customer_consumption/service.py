"""Daily consumption per tariff band of one customer (US-13, T-13.2).

Until the clean layer is served (sprint 4), the consumption of a meter comes
from the same deterministic model the F3 simulator sends
(`simulators.common.consumption.half_hour_kwh`, same SIM_SEED). So the API
returns exactly what the pipeline will produce once it cleans F3:

* every 30-minute reading of the month, valued with the model;
* the days a meter goes silent in F3 (missing-day defect, DEFECT_RATE) are the
  days RN-03 fills by profile, so all their readings count as estimated.


When the clean layer exists, only `_meter_readings` changes; the response stays.

Access rule (RN-11, CA-10, T-13.3): `ConsumptionService.daily` checks who is
asking before reading anything, so no router, job or future endpoint can skip it.
"""


import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import Depends

from seed.defects import should_skip_day
from simulators.common.consumption import HALF_HOUR, half_hour_kwh
from simulators.concentrator.generator import _rng

from app.api.common import Principal
from app.api.customer_consumption.repository import ConsumptionRepository, get_repository
from app.core.config import get_settings
from app.core.tariffs import BANDS, TariffCalendar, get_tariffs

KWH = Decimal("0.001")
MONEY = Decimal("0.0001")


@dataclass(frozen=True)
class Reading:
    interval_start: datetime
    energy_kwh: float
    estimated: bool


def month_bounds(month: str) -> tuple[datetime, datetime]:
    year, mon = map(int, month.split("-"))
    start = datetime(year, mon, 1, tzinfo=timezone.utc)
    days = calendar.monthrange(year, mon)[1]
    return start, start + timedelta(days=days)


def is_missing_day(meter_id: str, day: date, seed: int, defect_rate: float) -> bool:
    """Same decision the F3 simulator takes for a silent day (see generator._readings)."""
    return should_skip_day(_rng(seed, "day", meter_id, day.isoformat()), defect_rate)


def _meter_readings(meter_id: str, start: datetime, end: datetime, seed: int, defect_rate: float) -> list[Reading]:
    readings, ts = [], start
    missing: dict[date, bool] = {}
    while ts < end:
        day = ts.date()
        if day not in missing:
            missing[day] = is_missing_day(meter_id, day, seed, defect_rate)
        readings.append(Reading(ts, half_hour_kwh(meter_id, ts, seed), missing[day]))
        ts += HALF_HOUR
    return readings


def daily_by_band(
    meter_ids: list[str],
    month: str,
    tariffs: TariffCalendar,
    seed: int,
    defect_rate: float,
) -> list[dict]:
    """One row per (day, band), ordered by day and band. Empty if the customer has no meters."""
    start, end = month_bounds(month)
    totals: dict[tuple[date, str], dict] = defaultdict(lambda: {"kwh": 0.0, "cost": Decimal(0), "readings": 0, "estimated": 0})
    for meter_id in meter_ids:
        for r in _meter_readings(meter_id, start, end, seed, defect_rate):
            band = tariffs.band_for(r.interval_start)
            row = totals[(r.interval_start.date(), band.band_name)]
            row["kwh"] += r.energy_kwh
            row["cost"] += Decimal(str(r.energy_kwh)) * band.price_per_kwh
            row["readings"] += 1
            row["estimated"] += int(r.estimated)

    order = {name: i for i, name in enumerate(BANDS)}
    rows = []
    for (day, band_name), t in sorted(totals.items(), key=lambda kv: (kv[0][0], order[kv[0][1]])):
        rows.append({
            "date": day,
            "band_name": band_name,
            "energy_kwh": Decimal(str(t["kwh"])).quantize(KWH),
            "cost": t["cost"].quantize(MONEY),
            "readings": t["readings"],
            "estimated_readings": t["estimated"],
        })
    return rows


# ---------- access rule and service (T-13.3) ----------

class AccessDenied(Exception):
    """A customer asked for another customer's data."""


class CustomerNotFound(Exception):
    """The customer code is not in F4."""


def can_read_consumption(principal: Principal, owner_code: str) -> bool:
    """RN-11: internal users read any customer; a customer only reads their own data."""
    if principal.role == "internal":
        return True
    return principal.role == "customer" and principal.customer_code == owner_code


class ConsumptionService:
    def __init__(self, repo: ConsumptionRepository, tariffs: TariffCalendar, seed: int, defect_rate: float):
        self.repo = repo
        self.tariffs = tariffs
        self.seed = seed
        self.defect_rate = defect_rate

    def daily(self, principal: Principal, customer_code: str, month: str) -> dict:
        # Checked before looking the customer up: a customer cannot even learn
        # whether another customer code exists (403, never 404).
        if not can_read_consumption(principal, customer_code):
            raise AccessDenied(customer_code)
        if not self.repo.customer_exists(customer_code):
            raise CustomerNotFound(customer_code)
        rows = daily_by_band(self.repo.meter_ids(customer_code), month, self.tariffs, self.seed, self.defect_rate)
        return {
            "customer_code": customer_code,
            "month": month,
            "has_estimated_readings": any(r["estimated_readings"] for r in rows),
            "days": rows,
        }


def get_service(
    repo: ConsumptionRepository = Depends(get_repository),
    tariffs: TariffCalendar = Depends(get_tariffs),
) -> ConsumptionService:
    settings = get_settings()
    return ConsumptionService(repo, tariffs, settings.model_seed, settings.defect_rate)
