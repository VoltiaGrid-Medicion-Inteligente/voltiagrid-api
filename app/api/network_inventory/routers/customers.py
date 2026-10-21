"""Customers of F4 (US-18, T-18.3)."""

from typing import Annotated

from fastapi import APIRouter, Path

from app.api.common import AUTH_ERRORS, CONFLICT, NOT_FOUND, VALIDATION, Page
from app.api.network_inventory.routers.deps import Internal, PageQuery, Service, SizeQuery
from app.api.network_inventory.schemas import AcornGrouped, CustomerIn, CustomerOut

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=CustomerOut, status_code=201, responses={**AUTH_ERRORS, **CONFLICT, **VALIDATION})
def create_customer(body: CustomerIn, service: Service, _: Internal):
    return service.create_customer(body)


@router.get("", response_model=Page[CustomerOut], responses={**AUTH_ERRORS, **VALIDATION})
def list_customers(service: Service, _: Internal, page: PageQuery = 1, size: SizeQuery = 50,
                   acorn_grouped: AcornGrouped | None = None):
    return service.list_customers(page, size, acorn_grouped)


@router.get("/{code}", response_model=CustomerOut, responses={**AUTH_ERRORS, **NOT_FOUND})
def get_customer(code: Annotated[str, Path(examples=["CU-MAC000002"])], service: Service, _: Internal):
    return service.get_customer(code)
