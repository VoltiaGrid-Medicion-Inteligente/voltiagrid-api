"""Data access of the network inventory API on the F4 ORM (US-18, T-18.2).

The only module of the API that builds queries. Lists return (rows, total) so
the service can paginate without loading the whole table.
"""

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.inventory import Circuit, Customer, Meter, Transformer


class InventoryRepository:
    def __init__(self, session: Session):
        self.session = session

    # ---------- helpers ----------

    def _page(self, query: Select, offset: int, limit: int) -> tuple[list[Any], int]:
        total = self.session.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
        rows = self.session.execute(query.offset(offset).limit(limit)).all()
        return rows, total or 0

    def add(self, obj) -> None:
        self.session.add(obj)
        self.session.flush()

    def commit(self) -> None:
        self.session.commit()

    # ---------- customers ----------

    def get_customer(self, code: str) -> Customer | None:
        return self.session.scalar(select(Customer).where(Customer.code == code))

    def list_customers(self, offset: int, limit: int, acorn_grouped: str | None = None):
        query = select(Customer).order_by(Customer.code)
        if acorn_grouped:
            query = query.where(Customer.acorn_grouped == acorn_grouped)
        return self._page(query, offset, limit)

    # ---------- circuits ----------

    def _circuits(self) -> Select:
        transformers = (
            select(func.count(Transformer.id)).where(Transformer.circuit_id == Circuit.id).correlate(Circuit).scalar_subquery()
        )
        return select(Circuit, transformers.label("transformers")).order_by(Circuit.code)

    def get_circuit(self, code: str) -> Circuit | None:
        return self.session.scalar(select(Circuit).where(Circuit.code == code))

    def get_circuit_with_count(self, code: str):
        return self.session.execute(self._circuits().where(Circuit.code == code)).first()

    def list_circuits(self, offset: int, limit: int):
        return self._page(self._circuits(), offset, limit)

    # ---------- transformers ----------

    def _transformers(self) -> Select:
        meters = select(func.count(Meter.id)).where(Meter.transformer_id == Transformer.id).correlate(Transformer).scalar_subquery()
        return (
            select(Transformer, Circuit.code.label("circuit_code"), meters.label("meters"))
            .join(Circuit, Transformer.circuit_id == Circuit.id)
            .order_by(Transformer.code)
        )

    def get_transformer(self, code: str) -> Transformer | None:
        return self.session.scalar(select(Transformer).where(Transformer.code == code))

    def get_transformer_with_count(self, code: str):
        return self.session.execute(self._transformers().where(Transformer.code == code)).first()

    def list_transformers(self, offset: int, limit: int, circuit_code: str | None = None):
        query = self._transformers()
        if circuit_code:
            query = query.where(Circuit.code == circuit_code)
        return self._page(query, offset, limit)

    # ---------- meters ----------

    def _meters(self) -> Select:
        return (
            select(Meter.lclid, Customer.code.label("customer_code"), Transformer.code.label("transformer_code"))
            .join(Customer, Meter.customer_id == Customer.id)
            .join(Transformer, Meter.transformer_id == Transformer.id)
            .order_by(Meter.lclid)
        )

    def get_meter(self, lclid: str):
        return self.session.execute(self._meters().where(Meter.lclid == lclid)).first()

    def meter_exists(self, lclid: str) -> bool:
        return self.session.scalar(select(Meter.id).where(Meter.lclid == lclid)) is not None

    def list_meters(self, offset: int, limit: int, transformer_code: str | None = None, customer_code: str | None = None):
        query = self._meters()
        if transformer_code:
            query = query.where(Transformer.code == transformer_code)
        if customer_code:
            query = query.where(Customer.code == customer_code)
        return self._page(query, offset, limit)
