"""Customer daily consumption API (US-13).

    uvicorn app.api.customer_consumption.main:app --port 8001
    open http://localhost:8001/docs

Daily consumption per tariff band of a customer for one month (RF-06), with
the estimated-readings flag (RN-03). A customer only reads their own data (RN-11):
the rule lives in `ConsumptionService`, the routers only translate its errors.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.api.auth import router as auth_router
from app.api.common import AUTH_ERRORS, NOT_FOUND, Health, Principal, get_principal
from app.api.customer_consumption.service import AccessDenied, ConsumptionService, CustomerNotFound, get_service
from app.core.config import get_settings
from app.core.errors import register_error_handlers

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"

app = FastAPI(
    title="VoltiaGrid customer consumption API",
    version="0.2.0",
    description="Daily consumption per tariff band for the authenticated customer (RF-06, RN-11).",
    root_path=get_settings().root_path,  # /consumption behind the load balancer (T-27.3)
)
register_error_handlers(app)
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
Service = Annotated[ConsumptionService, Depends(get_service)]


def _daily(service: ConsumptionService, principal: Principal, customer_code: str, month: str) -> dict:
    try:
        return service.daily(principal, customer_code, month)
    except AccessDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Customers can only read their own consumption") from exc
    except CustomerNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Customer '{customer_code}' not found") from exc


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
def my_daily_consumption(month: MonthQuery, service: Service, principal: Principal = Depends(get_principal)):
    if principal.role != "customer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Use /customers/{customer_code}/consumption/daily")
    return _daily(service, principal, principal.customer_code, month)


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
    service: Service,
    principal: Principal = Depends(get_principal),
):
    return _daily(service, principal, customer_code, month)
