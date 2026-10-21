"""Meters of F4 (US-18, T-18.3)."""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.common import AUTH_ERRORS, CONFLICT, NOT_FOUND, VALIDATION, Page
from app.api.network_inventory.routers.deps import Internal, PageQuery, Service, SizeQuery
from app.api.network_inventory.schemas import MeterIn, MeterOut

router = APIRouter(prefix="/meters", tags=["meters"])


@router.post("", response_model=MeterOut, status_code=201, responses={**AUTH_ERRORS, **NOT_FOUND, **CONFLICT, **VALIDATION})
def create_meter(body: MeterIn, service: Service, _: Internal):
    return service.create_meter(body)


@router.get("", response_model=Page[MeterOut], responses={**AUTH_ERRORS, **VALIDATION})
def list_meters(
    service: Service,
    _: Internal,
    page: PageQuery = 1,
    size: SizeQuery = 50,
    transformer_code: Annotated[str | None, Query(examples=["TR-00000"])] = None,
    customer_code: Annotated[str | None, Query(examples=["CU-MAC000002"])] = None,
):
    return service.list_meters(page, size, transformer_code, customer_code)


@router.get("/{lclid}", response_model=MeterOut, responses={**AUTH_ERRORS, **NOT_FOUND})
def get_meter(lclid: Annotated[str, Path(examples=["MAC000002"])], service: Service, _: Internal):
    return service.get_meter(lclid)
