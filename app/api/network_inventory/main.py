from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from app.api.common import ErrorResponse, HealthResponse, Principal, get_principal

app = FastAPI(title="Network inventory")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()

class CustomerCreate(BaseModel):
    code: str
    name: str

class Customer(BaseModel):
    code: str
    name: str

class Meter(BaseModel):
    code: str
    customer_code: str
    transformer_code: str

class Transformer(BaseModel):
    code: str
    capacity_kva: float

_DB_CUSTOMERS: dict[str, Customer] = {
    "MAC000002": Customer(code="MAC000002", name="Demo"),
}


def _require_internal(principal: Principal) -> None:
    if principal.kind != "internal":
        raise HTTPException(status_code=403, detail="Only internal")


@app.post(
    "/customers",
    response_model=Customer,
    status_code=201,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def create_customer(
    body: CustomerCreate,
    principal: Annotated[Principal, Depends(get_principal)],
) -> Customer:
    _require_internal(principal)
    if body.code in _DB_CUSTOMERS:
        raise HTTPException(status_code=409, detail="Customer exists")
    cust = Customer(code=body.code, name=body.name)
    _DB_CUSTOMERS[body.code] = cust
    return cust


@app.get(
    "/customers/{code}",
    response_model=Customer,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_customer(
    code: str,
    principal: Annotated[Principal, Depends(get_principal)],
) -> Customer:
    _require_internal(principal)
    if code not in _DB_CUSTOMERS:
        raise HTTPException(status_code=404, detail="Not found")
    return _DB_CUSTOMERS[code]

from fastapi import Query

from app.api.common import Page

_METERS = [
    Meter(code="M-001", customer_code="MAC000002", transformer_code="TR-00001"),
    Meter(code="M-002", customer_code="MAC000003", transformer_code="TR-00001"),
    Meter(code="M-003", customer_code="MAC000004", transformer_code="TR-00002"),
]

_TRANSFORMERS = [
    Transformer(code="TR-00001", capacity_kva=100.0),
    Transformer(code="TR-00002", capacity_kva=50.0),
]


@app.get(
    "/meters",
    response_model=Page[Meter],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def list_meters(
    transformer_code: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    principal: Annotated[Principal, Depends(get_principal)] = None,  # type: ignore
) -> Page[Meter]:
    _require_internal(principal)
    items = _METERS
    if transformer_code:
        items = [m for m in items if m.transformer_code == transformer_code]
    total = len(items)
    return Page[Meter](items=items[offset : offset + limit], total=total, limit=limit, offset=offset)


@app.get(
    "/transformers",
    response_model=Page[Transformer],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def list_transformers(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    principal: Annotated[Principal, Depends(get_principal)] = None,  # type: ignore
) -> Page[Transformer]:
    _require_internal(principal)
    total = len(_TRANSFORMERS)
    return Page[Transformer](
        items=_TRANSFORMERS[offset : offset + limit], total=total, limit=limit, offset=offset
    )


@app.get(
    "/transformers/{code}",
    response_model=Transformer,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_transformer(
    code: str,
    principal: Annotated[Principal, Depends(get_principal)],
) -> Transformer:
    _require_internal(principal)
    for t in _TRANSFORMERS:
        if t.code == code:
            return t
    raise HTTPException(status_code=404, detail="Not found")

