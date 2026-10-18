"""Where the consumption API reads the customer and its meters (US-13, T-13.2).

Routers and services never touch the session: they ask a repository.
`SqlConsumptionRepository` reads F4; `InMemoryConsumptionRepository` is for
tests that must run without a database.
"""

from typing import Protocol

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.models.inventory import Customer, Meter


class ConsumptionRepository(Protocol):
    def customer_exists(self, customer_code: str) -> bool: ...

    def meter_ids(self, customer_code: str) -> list[str]: ...


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


class InMemoryConsumptionRepository:
    def __init__(self, meters_by_customer: dict[str, list[str]]):
        self.meters_by_customer = meters_by_customer

    def customer_exists(self, customer_code: str) -> bool:
        return customer_code in self.meters_by_customer

    def meter_ids(self, customer_code: str) -> list[str]:
        return self.meters_by_customer.get(customer_code, [])


def get_repository(session: Session = Depends(get_session)) -> ConsumptionRepository:
    return SqlConsumptionRepository(session)
