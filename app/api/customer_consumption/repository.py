"""Where the consumption API reads the customer and its meters (US-13, T-13.2).

Routers and services never touch the session: they ask a repository.
`SqlConsumptionRepository` reads F4, the precomputed `consumption_daily`
(US-47) and the demand-response participation (US-44);
`InMemoryConsumptionRepository` is for tests that must run without a database.
"""

from datetime import date
from typing import Protocol

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.models.consumption import ConsumptionDaily
from app.models.demand_response import DrParticipation
from app.models.inventory import Customer, Meter


class ConsumptionRepository(Protocol):
    def customer_exists(self, customer_code: str) -> bool: ...

    def meter_ids(self, customer_code: str) -> list[str]: ...

    def stored_daily(self, customer_code: str, first: date, last: date) -> list[dict]: ...

    def events(self, customer_code: str, first: date, last: date) -> list[dict]: ...


class SqlConsumptionRepository:
    def __init__(self, session: Session):
        self.session = session

    def customer_exists(self, customer_code: str) -> bool:
        return self.session.scalar(select(Customer.id).where(Customer.code == customer_code)) is not None

    def meter_ids(self, customer_code: str) -> list[str]:
        query = (
            select(Meter.lclid)
            .join(Customer, Meter.customer_id == Customer.id)
            .where(Customer.code == customer_code)
            .order_by(Meter.lclid)
        )
        return list(self.session.scalars(query))

    def stored_daily(self, customer_code: str, first: date, last: date) -> list[dict]:
        """Precomputed rows of the month (one indexed range read on the primary key), [] if not built."""
        query = (
            select(ConsumptionDaily)
            .where(ConsumptionDaily.customer_code == customer_code, ConsumptionDaily.date.between(first, last))
            .order_by(ConsumptionDaily.date)
        )
        return [{"date": r.date, "band_name": r.band_name, "energy_kwh": r.energy_kwh, "cost": r.cost,
                 "readings": r.readings, "estimated_readings": r.estimated_readings}
                for r in self.session.scalars(query)]

    def events(self, customer_code: str, first: date, last: date) -> list[dict]:
        """Demand-response events of the customer in those days, oldest first (index customer_code, event_date)."""
        query = (
            select(DrParticipation)
            .where(DrParticipation.customer_code == customer_code, DrParticipation.event_date.between(first, last))
            .order_by(DrParticipation.event_date, DrParticipation.event_id)
        )
        return [{"event_id": r.event_id, "event_date": r.event_date, "start": r.start_ts, "end": r.end_ts,
                 "baseline_kwh": r.baseline_kwh, "actual_kwh": r.actual_kwh, "savings_kwh": r.savings_kwh,
                 "savings_pct": r.savings_pct, "incentive_paid": r.incentive_paid,
                 "incentive_amount": r.incentive_amount}
                for r in self.session.scalars(query)]


class InMemoryConsumptionRepository:
    def __init__(self, meters_by_customer: dict[str, list[str]]):
        self.meters_by_customer = meters_by_customer

    def customer_exists(self, customer_code: str) -> bool:
        return customer_code in self.meters_by_customer

    def meter_ids(self, customer_code: str) -> list[str]:
        return self.meters_by_customer.get(customer_code, [])

    def stored_daily(self, customer_code: str, first: date, last: date) -> list[dict]:
        return []

    def events(self, customer_code: str, first: date, last: date) -> list[dict]:
        return []


def get_repository(session: Session = Depends(get_session)) -> ConsumptionRepository:
    return SqlConsumptionRepository(session)
