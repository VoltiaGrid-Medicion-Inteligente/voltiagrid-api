"""Daily consumption per customer, day and tariff band, precomputed for the customer API (US-47, T-47.2).

One row per customer, day and band: what `GET /me/consumption/daily` returns, so a month is one indexed read of
about 90 rows instead of computing 1,488 half hours per meter on every request. Filled by
`python -m scripts.build_consumption_daily`; a month without rows is still computed on the fly.
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ConsumptionDaily(Base):
    __tablename__ = "consumption_daily"

    # The primary key (customer_code, date, band_name) is also the index of the monthly query.
    customer_code: Mapped[str] = mapped_column(String(30), ForeignKey("customer.code"), primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    band_name: Mapped[str] = mapped_column(String(20), primary_key=True)
    energy_kwh: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    readings: Mapped[int] = mapped_column(Integer)
    estimated_readings: Mapped[int] = mapped_column(Integer)
