from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from app.api.common import (
    ErrorResponse,
    HealthResponse,
    Principal,
    add_error_handlers,
    get_principal,
)

app = FastAPI(title="Control center")
add_error_handlers(app)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


class LoadPoint(BaseModel):
    timestamp: str
    load_kw: float
    utilization_pct: float = 0.0

class TransformerLoadResponse(BaseModel):
    transformer_code: str
    capacity_kva: float
    points: list[LoadPoint]

class OverloadAlert(BaseModel):
    transformer_code: str
    load_kw: float
    capacity_kva: float

_KNOWN = {"TR-00001": 100.0, "TR-00002": 50.0}

@app.get(
    "/transformers/{transformer_code}/load",
    response_model=TransformerLoadResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_load(
    transformer_code: str,
    principal: Annotated[Principal, Depends(get_principal)],
    start: Annotated[str | None, Query()] = None,
    end: Annotated[str | None, Query()] = None,
) -> TransformerLoadResponse:
    if principal.kind != "internal":
        raise HTTPException(status_code=403, detail="Only internal can view loads")
    if transformer_code not in _KNOWN:
        raise HTTPException(status_code=404, detail="Transformer not found")
    cap = _KNOWN[transformer_code]
    pts = [
        LoadPoint(timestamp="2013-02-01T00:00:00Z", load_kw=120.5, utilization_pct=round(120.5 / cap * 100, 1)),
        LoadPoint(timestamp="2013-02-01T00:30:00Z", load_kw=118.2, utilization_pct=round(118.2 / cap * 100, 1)),
    ]
    return TransformerLoadResponse(transformer_code=transformer_code, capacity_kva=cap, points=pts)

@app.get(
    "/alerts/overload",
    response_model=list[OverloadAlert],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def get_overload(
    principal: Annotated[Principal, Depends(get_principal)],
) -> list[OverloadAlert]:
    if principal.kind != "internal":
        raise HTTPException(status_code=403, detail="Only internal can view alerts")
    return [
        OverloadAlert(transformer_code="TR-00001", load_kw=150.0, capacity_kva=100.0),
    ]