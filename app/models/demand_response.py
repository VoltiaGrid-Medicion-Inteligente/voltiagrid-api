"""Demand-response participation of each customer (US-44, T-44.4).

Written by voltiagrid-data (`python -m jobs.publish_dr`) from the settled events in the lake; read by the customer
consumption API (`GET /me/events`). One row per event and customer.
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DrParticipation(Base):
    __tablename__ = "dr_participation"
    __table_args__ = (
        UniqueConstraint("event_id", "customer_code"),
        Index("ix_dr_participation_customer_code_event_date", "customer_code", "event_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(40))
    customer_code: Mapped[str] = mapped_column(String(30), ForeignKey("customer.code"))
    event_date: Mapped[dt.date] = mapped_column(Date)
    start_ts: Mapped[dt.datetime] = mapped_column(DateTime)
    end_ts: Mapped[dt.datetime] = mapped_column(DateTime)
    baseline_kwh: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    actual_kwh: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    savings_kwh: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    savings_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    incentive_paid: Mapped[bool] = mapped_column(Boolean)
    incentive_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
