from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from app.api.common import ErrorResponse, HealthResponse, Principal, get_principal

app = FastAPI(title="Control center")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()



class LoadPoint(BaseModel):
    timestamp: str
    load_kw: float

class TransformerLoadResponse(BaseModel):
    transformer_code: str
    points: list[LoadPoint]

class OverloadAlert(BaseModel):
    transformer_code: str
    load_kw: float
    capacity_kva: float

@app.get(
    "/transformers/{transformer_code}/load",
    response_model=TransformerLoadResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def get_load(
    transformer_code: str,
    principal: Annotated[Principal, Depends(get_principal)],
) -> TransformerLoadResponse:
    if principal.kind != "internal":
        raise HTTPException(status_code=403, detail="Only internal can view loads")
    return TransformerLoadResponse(
        transformer_code=transformer_code,
        points=[
            LoadPoint(timestamp="2013-02-01T00:00:00Z", load_kw=120.5),
            LoadPoint(timestamp="2013-02-01T00:30:00Z", load_kw=118.2),
        ],
    )

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