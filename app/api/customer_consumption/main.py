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

app = FastAPI(title="Customer consumption")
add_error_handlers(app)

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()

class DailyItem(BaseModel):
    date: str
    peak_kwh: float
    intermediate_kwh: float
    offpeak_kwh: float
    peak_cost: float = 0.0
    intermediate_cost: float = 0.0
    offpeak_cost: float = 0.0
    estimated: bool = False

class DailyConsumptionResponse(BaseModel):
    customer_code: str
    month: str
    days: list[DailyItem]

@app.get(
    "/me/consumption/daily",
    response_model=DailyConsumptionResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def get_my_daily(
    month: Annotated[str, Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")],
    principal: Annotated[Principal, Depends(get_principal)], 
) -> DailyConsumptionResponse:
    if principal.kind != "customer":
        raise HTTPException(status_code=403, detail="Only customers can use /me")
    assert principal.customer_code is not None
    return DailyConsumptionResponse(
        customer_code=principal.customer_code,
        month=month,
        days=[
            DailyItem(
                date=f"{month}-01", 
                peak_kwh=5.2, 
                intermediate_kwh=2.0,
                offpeak_kwh=3.1,
                peak_cost=1.1,
                intermediate_cost=0.4,
                offpeak_cost=0.5,
                estimated=False,
                ),
            DailyItem(
                date=f"{month}-02",
                peak_kwh=4.9,
                intermediate_kwh=1.8,
                offpeak_kwh=2.8, 
                peak_cost=1.0,
                intermediate_cost=0.35,
                offpeak_cost=0.45,
                estimated=True,
                ),
        ],
    )


@app.get(
    "/customers/{customer_code}/consumption/daily",
    response_model=DailyConsumptionResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def get_customer_daily(
    customer_code: str,
    month: Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")],
    principal: Annotated[Principal, Depends(get_principal)],
) -> DailyConsumptionResponse:
    if principal.kind == "customer" and principal.customer_code != customer_code:
        raise HTTPException(status_code=403, detail="Cannot view other customer")
    return DailyConsumptionResponse(
        customer_code=customer_code,
        month=month,
        days=[
            DailyItem(
                date=f"{month}-01",
                peak_kwh=5.2, 
                intermediate_kwh=2.0,
                offpeak_kwh=3.1, 
                peak_cost=1.1,
                intermediate_cost= 0.4,
                offpeak_cost=0.5,
                estimated=False,
                ),
            DailyItem(
                date=f"{month}-02",
                peak_kwh=4.9, 
                inmtermediate_kwh=1.8,
                offpeak_kwh=2.8, 
                peak_cost=1.0,
                intermediate_cost=0.35,
                offpeak_cost=0.45,
                estimated=True,
                ),
        ],
    )