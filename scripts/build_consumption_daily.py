"""Precompute the customer API's daily consumption into consumption_daily (US-47, T-47.2).

    python -m scripts.build_consumption_daily --month 2013-01 --month 2013-02     # DATABASE_URL from .env
    python -m scripts.build_consumption_daily --from 2012-01 --to 2014-02

For every customer of F4 and every month given it stores exactly what `GET /me/consumption/daily` would compute (the
same `daily_by_band`, same seed and defect rate), replacing that customer-month. After it, the API answers those
months with one indexed read. Run it again after a new seed; a month not built keeps being computed on the fly.
"""

import argparse
import time

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.customer_consumption.service import daily_by_band, month_days
from app.core.config import get_settings
from app.core.db import get_engine
from app.core.tariffs import TariffCalendar
from app.models.consumption import ConsumptionDaily
from app.models.inventory import Customer, Meter


def months_between(first: str, last: str) -> list[str]:
    y, m = map(int, first.split("-"))
    months = []
    while f"{y:04d}-{m:02d}" <= last:
        months.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


def meters_by_customer(session: Session) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for code, lclid in session.execute(select(Customer.code, Meter.lclid).join(Meter, Meter.customer_id == Customer.id)
                                       .order_by(Customer.code, Meter.lclid)):
        result.setdefault(code, []).append(lclid)
    return result


def build(session: Session, months: list[str], tariffs: TariffCalendar, seed: int, defect_rate: float) -> int:
    """Replace every customer-month given; returns the rows written. Commits once per month."""
    customers = meters_by_customer(session)
    written = 0
    for month in months:
        first, last = month_days(month)
        session.execute(delete(ConsumptionDaily).where(ConsumptionDaily.date.between(first, last)))
        for code, meters in customers.items():
            rows = daily_by_band(meters, month, tariffs, seed, defect_rate)
            session.add_all(ConsumptionDaily(customer_code=code, **r) for r in rows)
            written += len(rows)
        session.commit()
    return written


def main() -> None:
    p = argparse.ArgumentParser(description="Precompute consumption_daily for the customer API (US-47)")
    p.add_argument("--month", action="append", default=[], metavar="YYYY-MM")
    p.add_argument("--from", dest="first", metavar="YYYY-MM")
    p.add_argument("--to", dest="last", metavar="YYYY-MM")
    args = p.parse_args()
    months = sorted(set(args.month) | set(months_between(args.first, args.last) if args.first and args.last else []))
    if not months:
        raise SystemExit("give --month YYYY-MM (repeatable) or --from YYYY-MM --to YYYY-MM")
    settings = get_settings()
    started = time.perf_counter()
    with Session(get_engine()) as session:
        rows = build(session, months, TariffCalendar.from_csv(settings.tariffs_csv), settings.model_seed,
                     settings.defect_rate)
    print(f"consumption_daily: {rows:,} rows for {len(months)} months in {time.perf_counter() - started:.0f} s")


if __name__ == "__main__":
    main()
