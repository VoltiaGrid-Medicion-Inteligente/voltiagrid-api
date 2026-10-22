"""Control center API (US-19).

    uvicorn app.api.control_center.main:app --port 8002
    open http://localhost:8002/docs

Load per transformer and overload alerts for control center operators
(internal users only). Load comes from F5 (energy delivered every 15 minutes)
and capacity from F4. Needs DATABASE_URL and F5_URL.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from pydantic import AwareDatetime, BaseModel, Field

from app.api.common import AUTH_ERRORS, ErrorResponse, Health, Principal, require_internal
from app.api.control_center.f5_client import F5Unavailable
from app.api.control_center.service import ControlCenterService, InvalidRange, get_service
from app.core.errors import register_error_handlers

F5_DOWN = {502: {"model": ErrorResponse, "description": "F5 transformer metering API is not available"}}

app = FastAPI(
    title="VoltiaGrid control center API",
    version="0.2.0",
    description="Load per transformer every 15 minutes and overload alerts (RF-07).",
)
register_error_handlers(app)


class LoadPoint(BaseModel):
    interval_start: AwareDatetime
    load_kw: Decimal = Field(description="average load in the interval = delivered kWh x 4", examples=["72.4"])
    capacity_pct: Decimal = Field(description="load_kw / capacity_kva x 100", examples=["51.3"])


class TransformerLoad(BaseModel):
    transformer_code: str = Field(examples=["TR-00001"])
    capacity_kva: Decimal = Field(examples=["141.00"])
    interval_minutes: int = 15
    points: list[LoadPoint]


class OverloadAlert(BaseModel):
    transformer_code: str = Field(examples=["TR-00002"])
    circuit_code: str = Field(examples=["CT-000"])
    interval_start: AwareDatetime
    load_kw: Decimal = Field(examples=["414.1"])
    capacity_kva: Decimal = Field(examples=["396.27"])
    capacity_pct: Decimal = Field(examples=["104.5"])


@app.get("/health", response_model=Health, tags=["health"])
def health():
    return Health()


@app.get(
    "/transformers/{transformer_code}/load",
    response_model=TransformerLoad,
    responses={
        **AUTH_ERRORS,
        404: {"model": ErrorResponse, "description": "Unknown transformer"},
        422: {"model": ErrorResponse, "description": "end before start, empty range or range above 7 days"},
        **F5_DOWN,
    },
    tags=["load"],
    summary="Load per 15-minute interval and % of capacity for one transformer",
)
def transformer_load(
    transformer_code: Annotated[str, Path(examples=["TR-00001"])],
    start: Annotated[AwareDatetime, Query(description="ISO 8601 with time zone", examples=["2013-03-04T00:00:00Z"])],
    end: Annotated[AwareDatetime, Query(description="exclusive", examples=["2013-03-05T00:00:00Z"])],
    service: Annotated[ControlCenterService, Depends(get_service)],
    _: Principal = Depends(require_internal),
):
    try:
        return service.load(transformer_code, start, end)
    except InvalidRange as exc:
        raise HTTPException(422, str(exc)) from exc
    except F5Unavailable as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "F5 transformer metering API is not available") from exc


@app.get(
        "/alerts/overload",
    response_model=list[OverloadAlert],
    responses={**AUTH_ERRORS, **F5_DOWN},
    tags=["alerts"],
    summary="Transformers above their capacity in the 15-minute interval that contains `at`",
)
def overload_alerts(
    service: Annotated[ControlCenterService, Depends(get_service)],
    _: Annotated[Principal, Depends(require_internal)],
    at: Annotated[AwareDatetime | None, Query(description="defaults to now (UTC)", examples=["2013-03-04T19:00:00Z"])] = None,
    circuit_code: Annotated[str | None, Query(description="only this circuit", examples=["CT-000"])] = None,
):
    try:
        return service.overload_alerts(at or datetime.now(timezone.utc), circuit_code)
    except F5Unavailable as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "F5 transformer metering API is not available") from exc