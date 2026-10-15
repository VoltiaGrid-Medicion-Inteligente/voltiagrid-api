"""Customer daily consumption API: OpenAPI stub (US-12, T-12.1). Implemented in US-13.

    uvicorn app.api.customer_consumption.main:app --port 8001
    open http://localhost:8001/docs

The routes, request parameters and response models are the contract. The data
returned now is a fixed example; US-13 replaces `_example_days` with the real
calculation without changing the contract.
"""

import calendar
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.api.common import AUTH_ERRORS, NOT_FOUND, Health, Principal, get_principal

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"

app = FastAPI(
    title="VoltiaGrid customer consumption API",
    version="0.1.0",
    description="Daily consumption per tariff band for the authenticated customer (RF-06, RN-11).",
)


class DailyBandConsumption(BaseModel):
    date: date
    band_name: Literal["peak", "intermediate", "off-peak"]
    energy_kwh: Decimal = Field(examples=["3.412"])
    cost: Decimal = Field(description="energy_kwh x band price (F7)", examples=["1.0236"])
    readings: int = Field(description="30-minute readings in the band that day", examples=[8])
    estimated_readings: int = Field(description="how many of them were estimated (RN-03)", examples=[0])


class DailyConsumptionResponse(BaseModel):
    customer_code: str = Field(examples=["CU-MAC000002"])
    month: str = Field(examples=["2013-03"])
    has_estimated_readings: bool
    days: list[DailyBandConsumption]


MonthQuery = Annotated[str, Query(pattern=MONTH_PATTERN, description="Month as YYYY-MM", examples=["2013-03"])]


def _example_days(month: str) -> list[DailyBandConsumption]:
    year, mon = map(int, month.split("-"))
    bands = [("off-peak", "4.100", "0.12", 20, 0), ("intermediate", "3.200", "0.18", 20, 1), ("peak", "2.500", "0.30", 8, 0)]
    days = []
    for day in range(1, calendar.monthrange(year, mon)[1] + 1):
        for band, kwh, price, readings, estimated in bands:
            days.append(DailyBandConsumption(
                date=date(year, mon, day), band_name=band, energy_kwh=Decimal(kwh),
                cost=(Decimal(kwh) * Decimal(price)).quantize(Decimal("0.0001")),
                readings=readings, estimated_readings=estimated,
            ))
    return days


def _response(customer_code: str, month: str) -> DailyConsumptionResponse:
    days = _example_days(month)
    return DailyConsumptionResponse(
        customer_code=customer_code, month=month,
        has_estimated_readings=any(d.estimated_readings for d in days), days=days,
    )


@app.get("/health", response_model=Health, tags=["health"])
def health():
    return Health()


@app.get(
    "/me/consumption/daily",
    response_model=DailyConsumptionResponse,
    responses=AUTH_ERRORS,
    tags=["consumption"],
    summary="Daily consumption per band of the authenticated customer",
)
def my_daily_consumption(month: MonthQuery, principal: Principal = Depends(get_principal)):
    if principal.role != "customer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Use /customers/{customer_code}/consumption/daily")
    return _response(principal.customer_code, month)


@app.get(
    "/customers/{customer_code}/consumption/daily",
    response_model=DailyConsumptionResponse,
    responses={**AUTH_ERRORS, **NOT_FOUND},
    tags=["consumption"],
    summary="Daily consumption per band of one customer (internal users, or the customer itself)",
)
def customer_daily_consumption(
    month: MonthQuery,
    customer_code: Annotated[str, Path(examples=["CU-MAC000002"])],
    principal: Principal = Depends(get_principal),
):
    # RN-11 / CA-10: a customer only reads their own data.
    if principal.role == "customer" and principal.customer_code != customer_code:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Customers can only read their own consumption")
    return _response(customer_code, month)
