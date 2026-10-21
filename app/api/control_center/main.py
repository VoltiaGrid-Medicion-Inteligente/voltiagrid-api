"""Control center API: OpenAPI stub (US-12, T-12.1). Implemented in US-19.

    uvicorn app.api.control_center.main:app --port 8002
    open http://localhost:8002/docs

Load per transformer and overload alerts for control center operators
(internal users only). The load comes from F5 (energy delivered every
15 minutes) in US-19; until then the data is a fixed example.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from pydantic import AwareDatetime, BaseModel, Field

from app.api.common import AUTH_ERRORS, ErrorResponse, Health, Principal, require_internal
from app.core.errors import register_error_handlers

MAX_RANGE = timedelta(days=7)
STEP = timedelta(minutes=15)
EXAMPLE_TRANSFORMERS = {"TR-00000": Decimal("155.82"), "TR-00001": Decimal("141.00"), "TR-00002": Decimal("396.27")}

app = FastAPI(
    title="VoltiaGrid control center API",
    version="0.1.0",
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
        422: {"model": ErrorResponse, "description": "end before start or range above 7 days"},
    },
    tags=["load"],
    summary="Load per 15-minute interval and % of capacity for one transformer",
)
def transformer_load(
    transformer_code: Annotated[str, Path(examples=["TR-00001"])],
    start: Annotated[AwareDatetime, Query(description="ISO 8601 with time zone", examples=["2013-03-04T00:00:00Z"])],
    end: Annotated[AwareDatetime, Query(description="exclusive", examples=["2013-03-05T00:00:00Z"])],
    _: Principal = Depends(require_internal),
):
    capacity = EXAMPLE_TRANSFORMERS.get(transformer_code)
    if capacity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Transformer '{transformer_code}' not found")
    if end <= start:
        raise HTTPException(422, "end must be after start")
    if end - start > MAX_RANGE:
        raise HTTPException(422, "range must be 7 days or less")
    points, ts = [], start
    while ts < end:
        load = Decimal("40") + Decimal(ts.hour * 2)
        points.append(LoadPoint(interval_start=ts, load_kw=load, capacity_pct=(load / capacity * 100).quantize(Decimal("0.1"))))
        ts += STEP
    return TransformerLoad(transformer_code=transformer_code, capacity_kva=capacity, points=points)


@app.get(
    "/alerts/overload",
    response_model=list[OverloadAlert],
    responses=AUTH_ERRORS,
    tags=["alerts"],
    summary="Transformers above their capacity in the 15-minute interval that contains `at`",
)
def overload_alerts(
    _: Annotated[Principal, Depends(require_internal)],
    at: Annotated[AwareDatetime | None, Query(description="defaults to now (UTC)", examples=["2013-03-04T19:00:00Z"])] = None,
):
    interval = (at or datetime.now().astimezone()).replace(second=0, microsecond=0)
    interval = interval.replace(minute=interval.minute - interval.minute % 15)
    return [OverloadAlert(transformer_code="TR-00002", circuit_code="CT-000", interval_start=interval,
                          load_kw=Decimal("414.1"), capacity_kva=Decimal("396.27"), capacity_pct=Decimal("104.5"))]
