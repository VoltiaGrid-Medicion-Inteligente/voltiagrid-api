"""F7 tariff calendar: which band and price apply to a reading (US-13, T-13.2).

The CSV is the same file validated in voltiagrid-data (data/reference/tariffs.csv):

    valid_from,valid_to,start_time,end_time,band_name,price_per_kwh
    2012-01-01,2099-12-31,18:00:00,21:59:59,peak,0.30

A 30-minute reading belongs to the band whose time window contains its start.
Times are read as UTC, the same clock as the F1 and F3 timestamps.
"""

import csv
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings

BANDS = ("peak", "intermediate", "off-peak")


@dataclass(frozen=True)
class TariffRow:
    valid_from: date
    valid_to: date
    start_time: time
    end_time: time
    band_name: str
    price_per_kwh: Decimal

    def applies_to(self, ts: datetime) -> bool:
        return self.valid_from <= ts.date() <= self.valid_to and self.start_time <= ts.time() <= self.end_time


class TariffCalendar:
    def __init__(self, rows: list[TariffRow]):
        if not rows:
            raise ValueError("empty tariff calendar")
        self.rows = rows

    @classmethod
    def from_csv(cls, path: str | Path) -> "TariffCalendar":
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = [
                TariffRow(
                    valid_from=date.fromisoformat(r["valid_from"]),
                    valid_to=date.fromisoformat(r["valid_to"]),
                    start_time=time.fromisoformat(r["start_time"]),
                    end_time=time.fromisoformat(r["end_time"]),
                    band_name=r["band_name"].strip(),
                    price_per_kwh=Decimal(r["price_per_kwh"]),
                )
                for r in csv.DictReader(f)
            ]
        return cls(rows)

    def band_for(self, ts: datetime) -> TariffRow:
        naive = ts.replace(tzinfo=None)
        for row in self.rows:
            if row.applies_to(naive):
                return row
        raise LookupError(f"no tariff band covers {ts.isoformat()}")


@lru_cache(maxsize=1)
def get_tariffs() -> TariffCalendar:
    """FastAPI dependency: the calendar is read once per process."""
    return TariffCalendar.from_csv(get_settings().tariffs_csv)
