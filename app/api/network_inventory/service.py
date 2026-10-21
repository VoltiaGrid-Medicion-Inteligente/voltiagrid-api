"""Business rules of the network inventory API (US-18, T-18.2).

Routers call this service and never touch the session. Errors are domain
errors (NotFoundError, ConflictError); T-18.3 maps them to HTTP.
"""

from decimal import Decimal

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.network_inventory.repository import InventoryRepository
from app.api.network_inventory.schemas import (
    CircuitIn,
    CircuitOut,
    CustomerIn,
    CustomerOut,
    MeterIn,
    MeterOut,
    TransformerIn,
    TransformerOut,
)
from app.core.db import get_session
from app.core.errors import ConflictError, NotFoundError
from app.models.inventory import Circuit, Customer, Meter, Transformer


def _page(items: list, page: int, size: int, total: int) -> dict:
    return {"items": items, "page": page, "size": size, "total": total}


def _offset(page: int, size: int) -> int:
    return (page - 1) * size


class InventoryService:
    def __init__(self, repo: InventoryRepository):
        self.repo = repo

    # ---------- customers ----------

    @staticmethod
    def _customer(c: Customer) -> CustomerOut:
        return CustomerOut(code=c.code, acorn_group=c.acorn_group, acorn_grouped=c.acorn_grouped)

    def create_customer(self, body: CustomerIn) -> CustomerOut:
        if self.repo.get_customer(body.code):
            raise ConflictError("Customer", body.code)
        customer = Customer(**body.model_dump())
        self.repo.add(customer)
        self.repo.commit()
        return self._customer(customer)

    def get_customer(self, code: str) -> CustomerOut:
        customer = self.repo.get_customer(code)
        if customer is None:
            raise NotFoundError("Customer", code)
        return self._customer(customer)

    def list_customers(self, page: int, size: int, acorn_grouped: str | None = None) -> dict:
        rows, total = self.repo.list_customers(_offset(page, size), size, acorn_grouped)
        return _page([self._customer(r.Customer) for r in rows], page, size, total)

    # ---------- circuits ----------

    @staticmethod
    def _circuit(row) -> CircuitOut:
        return CircuitOut(code=row.Circuit.code, capacity_kva=row.Circuit.capacity_kva, transformers=row.transformers)

    def create_circuit(self, body: CircuitIn) -> CircuitOut:
        if self.repo.get_circuit(body.code):
            raise ConflictError("Circuit", body.code)
        self.repo.add(Circuit(**body.model_dump()))
        self.repo.commit()
        return self.get_circuit(body.code)

    def get_circuit(self, code: str) -> CircuitOut:
        row = self.repo.get_circuit_with_count(code)
        if row is None:
            raise NotFoundError("Circuit", code)
        return self._circuit(row)

    def list_circuits(self, page: int, size: int) -> dict:
        rows, total = self.repo.list_circuits(_offset(page, size), size)
        return _page([self._circuit(r) for r in rows], page, size, total)

    def update_circuit_capacity(self, code: str, capacity_kva: Decimal) -> CircuitOut:
        circuit = self.repo.get_circuit(code)
        if circuit is None:
            raise NotFoundError("Circuit", code)
        circuit.capacity_kva = capacity_kva
        self.repo.commit()
        return self.get_circuit(code)

    # ---------- transformers ----------

    @staticmethod
    def _transformer(row) -> TransformerOut:
        t = row.Transformer
        return TransformerOut(code=t.code, circuit_code=row.circuit_code, capacity_kva=t.capacity_kva, meters=row.meters)

    def create_transformer(self, body: TransformerIn) -> TransformerOut:
        if self.repo.get_transformer(body.code):
            raise ConflictError("Transformer", body.code)
        circuit = self.repo.get_circuit(body.circuit_code)
        if circuit is None:
            raise NotFoundError("Circuit", body.circuit_code)
        self.repo.add(Transformer(code=body.code, circuit_id=circuit.id, capacity_kva=body.capacity_kva))
        self.repo.commit()
        return self.get_transformer(body.code)

    def get_transformer(self, code: str) -> TransformerOut:
        row = self.repo.get_transformer_with_count(code)
        if row is None:
            raise NotFoundError("Transformer", code)
        return self._transformer(row)

    def list_transformers(self, page: int, size: int, circuit_code: str | None = None) -> dict:
        rows, total = self.repo.list_transformers(_offset(page, size), size, circuit_code)
        return _page([self._transformer(r) for r in rows], page, size, total)

    def update_transformer_capacity(self, code: str, capacity_kva: Decimal) -> TransformerOut:
        transformer = self.repo.get_transformer(code)
        if transformer is None:
            raise NotFoundError("Transformer", code)
        transformer.capacity_kva = capacity_kva
        self.repo.commit()
        return self.get_transformer(code)

    # ---------- meters ----------

    @staticmethod
    def _meter(row) -> MeterOut:
        return MeterOut(lclid=row.lclid, customer_code=row.customer_code, transformer_code=row.transformer_code)

    def create_meter(self, body: MeterIn) -> MeterOut:
        if self.repo.meter_exists(body.lclid):
            raise ConflictError("Meter", body.lclid)
        customer = self.repo.get_customer(body.customer_code)
        if customer is None:
            raise NotFoundError("Customer", body.customer_code)
        transformer = self.repo.get_transformer(body.transformer_code)
        if transformer is None:
            raise NotFoundError("Transformer", body.transformer_code)
        self.repo.add(Meter(lclid=body.lclid, customer_id=customer.id, transformer_id=transformer.id))
        self.repo.commit()
        return self.get_meter(body.lclid)

    def get_meter(self, lclid: str) -> MeterOut:
        row = self.repo.get_meter(lclid)
        if row is None:
            raise NotFoundError("Meter", lclid)
        return self._meter(row)

    def list_meters(self, page: int, size: int, transformer_code: str | None = None, customer_code: str | None = None) -> dict:
        rows, total = self.repo.list_meters(_offset(page, size), size, transformer_code, customer_code)
        return _page([self._meter(r) for r in rows], page, size, total)


def get_inventory_service(session: Session = Depends(get_session)) -> InventoryService:
    return InventoryService(InventoryRepository(session))
