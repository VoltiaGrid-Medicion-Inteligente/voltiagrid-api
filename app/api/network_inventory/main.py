"""Network inventory API (F4): OpenAPI stub (US-12, T-12.1). Implemented in US-18.

    uvicorn app.api.network_inventory.main:app --port 8003
    open http://localhost:8003/docs

Customers, circuits, transformers and meters of the F4 inventory, for internal
users. Resources are identified by their natural key (code or lclid), never by
the internal id. The data lives in memory until US-18 connects the routes to the ORM.
"""

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.api.common import AUTH_ERRORS, NOT_FOUND, ErrorResponse, Health, Page, Principal, require_internal

app = FastAPI(
    title="VoltiaGrid network inventory API",
    version="0.1.0",
    description="Customers, circuits, transformers and meters of the network inventory (F4).",
)

CONFLICT = {409: {"model": ErrorResponse, "description": "The natural key already exists"}}
Internal = Annotated[Principal, Depends(require_internal)]
PageQuery = Annotated[int, Query(ge=1, description="Page number, from 1")]
SizeQuery = Annotated[int, Query(ge=1, le=200, description="Items per page, max 200")]
AcornGrouped = Literal["Affluent", "Comfortable", "Adversity", "Unknown"]
Capacity = Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2, examples=["250.00"])]


# ---------- schemas (same fields as app/models/inventory.py) ----------

class CustomerIn(BaseModel):
    code: str = Field(min_length=1, max_length=30, examples=["CU-MAC009999"])
    acorn_group: str = Field(min_length=1, max_length=30, examples=["ACORN-E"])
    acorn_grouped: AcornGrouped


class CustomerOut(CustomerIn):
    pass


class CircuitIn(BaseModel):
    code: str = Field(min_length=1, max_length=20, examples=["CT-001"])
    capacity_kva: Capacity


class CircuitOut(CircuitIn):
    transformers: int = Field(description="number of transformers in the circuit", examples=[7])


class TransformerIn(BaseModel):
    code: str = Field(min_length=1, max_length=20, examples=["TR-00099"])
    circuit_code: str = Field(min_length=1, max_length=20, examples=["CT-000"])
    capacity_kva: Capacity


class TransformerOut(TransformerIn):
    meters: int = Field(description="number of meters connected", examples=[64])


class CapacityUpdate(BaseModel):
    capacity_kva: Capacity


class MeterIn(BaseModel):
    lclid: str = Field(min_length=1, max_length=20, examples=["MAC009999"])
    customer_code: str = Field(min_length=1, max_length=30, examples=["CU-MAC009999"])
    transformer_code: str = Field(min_length=1, max_length=20, examples=["TR-00000"])


class MeterOut(MeterIn):
    pass


# ---------- example data (replaced by the ORM in US-18) ----------

_customers = {
    "CU-MAC000002": CustomerOut(code="CU-MAC000002", acorn_group="ACORN-A", acorn_grouped="Affluent"),
    "CU-MAC000003": CustomerOut(code="CU-MAC000003", acorn_group="ACORN-P", acorn_grouped="Adversity"),
}
_circuits = {"CT-000": CircuitOut(code="CT-000", capacity_kva=Decimal("2100.12"), transformers=2)}
_transformers = {
    "TR-00000": TransformerOut(code="TR-00000", circuit_code="CT-000", capacity_kva=Decimal("155.82"), meters=2),
    "TR-00001": TransformerOut(code="TR-00001", circuit_code="CT-000", capacity_kva=Decimal("141.00"), meters=1),
}
_meters = {
    "MAC000002": MeterOut(lclid="MAC000002", customer_code="CU-MAC000002", transformer_code="TR-00000"),
    "MAC000003": MeterOut(lclid="MAC000003", customer_code="CU-MAC000003", transformer_code="TR-00000"),
    "MAC000004": MeterOut(lclid="MAC000004", customer_code="CU-MAC000003", transformer_code="TR-00001"),
}


def _page(items: list, page: int, size: int) -> dict:
    start = (page - 1) * size
    return {"items": items[start:start + size], "page": page, "size": size, "total": len(items)}


def _get(store: dict, key: str, label: str):
    if key not in store:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} '{key}' not found")
    return store[key]


def _add(store: dict, key: str, label: str, item):
    if key in store:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{label} '{key}' already exists")
    store[key] = item
    return item


# ---------- routes ----------

@app.get("/health", response_model=Health, tags=["health"])
def health():
    return Health()


@app.post("/customers", response_model=CustomerOut, status_code=201, responses={**AUTH_ERRORS, **CONFLICT}, tags=["customers"])
def create_customer(body: CustomerIn, _: Internal):
    return _add(_customers, body.code, "Customer", CustomerOut(**body.model_dump()))


@app.get("/customers", response_model=Page[CustomerOut], responses=AUTH_ERRORS, tags=["customers"])
def list_customers(_: Internal, page: PageQuery = 1, size: SizeQuery = 50, acorn_grouped: AcornGrouped | None = None):
    items = [c for c in _customers.values() if acorn_grouped is None or c.acorn_grouped == acorn_grouped]
    return _page(items, page, size)


@app.get("/customers/{code}", response_model=CustomerOut, responses={**AUTH_ERRORS, **NOT_FOUND}, tags=["customers"])
def get_customer(code: Annotated[str, Path(examples=["CU-MAC000002"])], _: Internal):
    return _get(_customers, code, "Customer")


@app.post("/circuits", response_model=CircuitOut, status_code=201, responses={**AUTH_ERRORS, **CONFLICT}, tags=["circuits"])
def create_circuit(body: CircuitIn, _: Internal):
    return _add(_circuits, body.code, "Circuit", CircuitOut(**body.model_dump(), transformers=0))


@app.get("/circuits", response_model=Page[CircuitOut], responses=AUTH_ERRORS, tags=["circuits"])
def list_circuits(_: Internal, page: PageQuery = 1, size: SizeQuery = 50):
    return _page(list(_circuits.values()), page, size)


@app.get("/circuits/{code}", response_model=CircuitOut, responses={**AUTH_ERRORS, **NOT_FOUND}, tags=["circuits"])
def get_circuit(code: Annotated[str, Path(examples=["CT-000"])], _: Internal):
    return _get(_circuits, code, "Circuit")


@app.patch("/circuits/{code}", response_model=CircuitOut, responses={**AUTH_ERRORS, **NOT_FOUND}, tags=["circuits"])
def update_circuit_capacity(code: Annotated[str, Path(examples=["CT-000"])], body: CapacityUpdate, _: Internal):
    circuit = _get(_circuits, code, "Circuit")
    _circuits[code] = circuit.model_copy(update={"capacity_kva": body.capacity_kva})
    return _circuits[code]


@app.post("/transformers", response_model=TransformerOut, status_code=201,
          responses={**AUTH_ERRORS, **NOT_FOUND, **CONFLICT}, tags=["transformers"])
def create_transformer(body: TransformerIn, _: Internal):
    _get(_circuits, body.circuit_code, "Circuit")
    return _add(_transformers, body.code, "Transformer", TransformerOut(**body.model_dump(), meters=0))


@app.get("/transformers", response_model=Page[TransformerOut], responses=AUTH_ERRORS, tags=["transformers"])
def list_transformers(
    _: Internal,
    page: PageQuery = 1,
    size: SizeQuery = 50,
    circuit_code: Annotated[str | None, Query(examples=["CT-000"])] = None,
):
    items = [t for t in _transformers.values() if circuit_code is None or t.circuit_code == circuit_code]
    return _page(items, page, size)


@app.get("/transformers/{code}", response_model=TransformerOut, responses={**AUTH_ERRORS, **NOT_FOUND}, tags=["transformers"])
def get_transformer(code: Annotated[str, Path(examples=["TR-00000"])], _: Internal):
    return _get(_transformers, code, "Transformer")


@app.patch("/transformers/{code}", response_model=TransformerOut, responses={**AUTH_ERRORS, **NOT_FOUND}, tags=["transformers"])
def update_transformer_capacity(code: Annotated[str, Path(examples=["TR-00000"])], body: CapacityUpdate, _: Internal):
    transformer = _get(_transformers, code, "Transformer")
    _transformers[code] = transformer.model_copy(update={"capacity_kva": body.capacity_kva})
    return _transformers[code]


@app.post("/meters", response_model=MeterOut, status_code=201, responses={**AUTH_ERRORS, **NOT_FOUND, **CONFLICT}, tags=["meters"])
def create_meter(body: MeterIn, _: Internal):
    _get(_customers, body.customer_code, "Customer")
    _get(_transformers, body.transformer_code, "Transformer")
    return _add(_meters, body.lclid, "Meter", MeterOut(**body.model_dump()))


@app.get("/meters", response_model=Page[MeterOut], responses=AUTH_ERRORS, tags=["meters"])
def list_meters(
    _: Internal,
    page: PageQuery = 1,
    size: SizeQuery = 50,
    transformer_code: Annotated[str | None, Query(examples=["TR-00000"])] = None,
    customer_code: Annotated[str | None, Query(examples=["CU-MAC000002"])] = None,
):
    items = [
        m for m in _meters.values()
        if (transformer_code is None or m.transformer_code == transformer_code)
        and (customer_code is None or m.customer_code == customer_code)
    ]
    return _page(items, page, size)


@app.get("/meters/{lclid}", response_model=MeterOut, responses={**AUTH_ERRORS, **NOT_FOUND}, tags=["meters"])
def get_meter(lclid: Annotated[str, Path(examples=["MAC000002"])], _: Internal):
    return _get(_meters, lclid, "Meter")
