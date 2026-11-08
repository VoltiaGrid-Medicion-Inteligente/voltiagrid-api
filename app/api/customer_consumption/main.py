"""Customer daily consumption API (US-13).

    uvicorn app.api.customer_consumption.main:app --port 8001
    open http://localhost:8001/docs

Daily consumption per tariff band of a customer for one month (RF-06), with
the estimated-readings flag (RN-03), and the customer's demand-response events
(US-44). A customer only reads their own data (RN-11): the rule lives in
`ConsumptionService`, the routers only translate its errors.
"""

import datetime as dt
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from fastapi.middleware.cors import CORSMiddleware
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
    description="Daily consumption per tariff band and demand-response events of the authenticated customer "
                "(RF-06, RN-09, RN-11).",
    root_path=get_settings().root_path,  # /consumption behind the load balancer (T-27.3)
)
register_error_handlers(app)
app.include_router(auth_router)
# The portal (voltiagrid-portal) calls this API from its own origin; the list comes from CORS_ORIGINS, never '*'.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().cors_origins),
    allow_methods=["GET"],
    allow_headers=["Authorization"],
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


class TransformerProfile(BaseModel):
    code: str = Field(examples=["TR-00001"])
    capacity_kva: Decimal = Field(examples=["100.00"])


class CircuitProfile(BaseModel):
    code: str = Field(examples=["CT-000"])


class MeterProfile(BaseModel):
    lclid: str = Field(examples=["MAC000002"])
    transformer: TransformerProfile
    circuit: CircuitProfile


class ProfileResponse(BaseModel):
    customer_code: str = Field(examples=["CU-MAC000002"])
    tariff_type: Literal["standard", "dynamic"] | None = Field(description="tariff of the latest contract; null without one")
    socioeconomic_group: str | None = Field(description="ACORN group (acorn_grouped)", examples=["Comfortable"])
    meters: list[MeterProfile]


class IntervalConsumption(BaseModel):
    start: datetime = Field(description="start of the half hour (UTC)", examples=["2013-03-01T00:00:00Z"])
    band_name: Literal["peak", "intermediate", "off-peak"]
    energy_kwh: Decimal = Field(examples=["0.412"])
    estimated: bool = Field(description="true when a meter's reading in this half hour was estimated (RN-03)")


class IntervalsResponse(BaseModel):
    customer_code: str = Field(examples=["CU-MAC000002"])
    date: dt.date = Field(examples=["2013-03-01"])
    intervals: list[IntervalConsumption] = Field(description="48 half hours of the day, in order")


class EventParticipation(BaseModel):
    event_id: str = Field(examples=["DR-CT-000-20130722"])
    event_date: date
    start: datetime = Field(description="event window start (UTC)", examples=["2013-07-22T19:00:00"])
    end: datetime = Field(description="event window end (UTC), 3 hours at most", examples=["2013-07-22T22:00:00"])
    baseline_kwh: Decimal | None = Field(description="average of the same window over the last 5 working days "
                                                     "without an event (RN-09); null without 5 days",
                                         examples=["7.2000"])
    actual_kwh: Decimal | None = Field(examples=["6.0000"])
    savings_kwh: Decimal | None = Field(examples=["1.2000"])
    savings_pct: Decimal | None = Field(description="savings / baseline", examples=["0.1667"])
    incentive_paid: bool = Field(description="savings of 10% or more (RN-09)")
    incentive_amount: Decimal = Field(examples=["0.36"])


class EventsResponse(BaseModel):
    customer_code: str = Field(examples=["CU-MAC000002"])
    month: str = Field(examples=["2013-07"])
    events: list[EventParticipation]
    incentives_total: Decimal = Field(examples=["0.36"])


MonthQuery = Annotated[str, Query(pattern=MONTH_PATTERN, description="Month as YYYY-MM", examples=["2013-03"])]
Service = Annotated[ConsumptionService, Depends(get_service)]


def _daily(service: ConsumptionService, principal: Principal, customer_code: str, month: str) -> dict:
    return _call(service.daily, principal, customer_code, month)


def _call(method, principal: Principal, customer_code: str, month: str) -> dict:
    try:
        return method(principal, customer_code, month)
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


@app.get(
    "/me/profile",
    response_model=ProfileResponse,
    responses={**AUTH_ERRORS, **NOT_FOUND},
    tags=["profile"],
    summary="Contract, socioeconomic group, meters, transformers and circuits of the authenticated customer",
)
def my_profile(service: Service, principal: Principal = Depends(get_principal)):
    if principal.role != "customer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Internal users read customers in the inventory API")
    try:
        return service.profile(principal, principal.customer_code)
    except CustomerNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Customer '{principal.customer_code}' not found") from exc


@app.get(
    "/me/consumption/intervals",
    response_model=IntervalsResponse,
    responses={**AUTH_ERRORS, **NOT_FOUND},
    tags=["consumption"],
    summary="The 48 half-hour readings of one day for the authenticated customer",
)
def my_intervals(
    day: Annotated[date, Query(alias="date", description="Day as YYYY-MM-DD", examples=["2013-03-01"])],
    service: Service,
    principal: Principal = Depends(get_principal),
):
    if principal.role != "customer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Internal users read intervals of a customer in the inventory API")
    try:
        return service.intervals(principal, principal.customer_code, day)
    except CustomerNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No readings for customer '{principal.customer_code}' on {day}") from exc


@app.get(
    "/me/events",
    response_model=EventsResponse,
    responses={**AUTH_ERRORS, **NOT_FOUND},
    tags=["demand response"],
    summary="Demand-response events of the authenticated customer in a month, with savings and incentive",
)
def my_events(month: MonthQuery, service: Service, principal: Principal = Depends(get_principal)):
    if principal.role != "customer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Use /customers/{customer_code}/events")
    return _call(service.events, principal, principal.customer_code, month)


@app.get(
    "/customers/{customer_code}/events",
    response_model=EventsResponse,
    responses={**AUTH_ERRORS, **NOT_FOUND},
    tags=["demand response"],
    summary="Demand-response events of one customer in a month (internal users, or the customer itself)",
)
def customer_events(
    month: MonthQuery,
    customer_code: Annotated[str, Path(examples=["CU-MAC000002"])],
    service: Service,
    principal: Principal = Depends(get_principal),
):
    return _call(service.events, principal, customer_code, month)
