"""Customer daily consumption API (US-13).

    uvicorn app.api.customer_consumption.main:app --port 8001
    open http://localhost:8001/docs

Daily consumption per tariff band of a customer for one month (RF-06), with
the estimated-readings flag (RN-03). A customer only reads their own data (RN-11).
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.api.auth import router as auth_router
from app.api.common import AUTH_ERRORS, NOT_FOUND, Health, Principal, get_principal
from app.api.customer_consumption.repository import ConsumptionRepository, get_repository
from app.api.customer_consumption.service import daily_by_band
from app.core.config import get_settings
from app.core.tariffs import TariffCalendar, get_tariffs

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"

app = FastAPI(
    title="VoltiaGrid customer consumption API",
    version="0.2.0",
    description="Daily consumption per tariff band for the authenticated customer (RF-06, RN-11).",
)
app.include_router(auth_router)


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
Repository = Annotated[ConsumptionRepository, Depends(get_repository)]
Tariffs = Annotated[TariffCalendar, Depends(get_tariffs)]


def _response(customer_code: str, month: str, repo: ConsumptionRepository, tariffs: TariffCalendar) -> DailyConsumptionResponse:
    if not repo.customer_exists(customer_code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Customer '{customer_code}' not found")
    settings = get_settings()
    rows = daily_by_band(repo.meter_ids(customer_code), month, tariffs, settings.model_seed, settings.defect_rate)
    return DailyConsumptionResponse(
        customer_code=customer_code,
        month=month,
        has_estimated_readings=any(r["estimated_readings"] for r in rows),
        days=[DailyBandConsumption(**r) for r in rows],
    )


@app.get("/health", response_model=Health, tags=["health"])
def health():
    return Health()


@app.get(
    "/me/consumption/daily",
    response_model=DailyConsumptionResponse,
    responses={**AUTH_ERRORS, **NOT_FOUND},
    tags=["consumption"],
    summary="Daily consumption per band of the authenticated customer",
)
def my_daily_consumption(month: MonthQuery, repo: Repository, tariffs: Tariffs, principal: Principal = Depends(get_principal)):
    if principal.role != "customer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Use /customers/{customer_code}/consumption/daily")
    return _response(principal.customer_code, month, repo, tariffs)


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
    repo: Repository,
    tariffs: Tariffs,
    principal: Principal = Depends(get_principal),
):
    # RN-11 / CA-10: a customer only reads their own data.
    if principal.role == "customer" and principal.customer_code != customer_code:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Customers can only read their own consumption")
    return _response(customer_code, month, repo, tariffs)
