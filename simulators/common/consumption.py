import hashlib
import math
from datetime import datetime, timedelta

HALF_HOUR = timedelta(minutes=30)
QUARTER_HOUR = timedelta(minutes=15)


def _unit(*parts) -> float:
    key = "|".join(str(p) for p in parts).encode()
    return int(hashlib.sha256(key).hexdigest()[:13], 16) / 16**13


def floor_to(ts: datetime, step: timedelta) -> datetime:
    minutes = int(step.total_seconds() // 60)
    return ts.replace(minute=ts.minute - ts.minute % minutes, second=0, microsecond=0)


def daily_profile(hour: float) -> float:
    morning = 0.35 * math.exp(-((hour - 7.5) ** 2) / 2.0)
    evening = 0.80 * math.exp(-((hour - 19.0) ** 2) / 4.5)
    return 0.25 + morning + evening


def meter_base_kwh(meter_id: str, seed: int) -> float:
    return 0.10 + 0.30 * _unit(seed, "base", meter_id)


def half_hour_kwh(meter_id: str, interval_start: datetime, seed: int) -> float:
    hour = interval_start.hour + interval_start.minute / 60
    noise = 0.85 + 0.30 * _unit(seed, "noise", meter_id, interval_start.isoformat())
    return round(meter_base_kwh(meter_id, seed) * daily_profile(hour) * noise, 3)


def quarter_hour_kwh(meter_id: str, interval_start: datetime, seed: int) -> float:
    half_start = floor_to(interval_start, HALF_HOUR)
    return half_hour_kwh(meter_id, half_start, seed) / 2