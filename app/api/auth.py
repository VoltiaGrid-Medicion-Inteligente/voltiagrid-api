"""Token endpoint for the demo (US-13, T-13.1).

    POST /auth/token  {"username": "CU-MAC000002", "password": "..."}  -> customer token
    POST /auth/token  {"username": "internal",     "password": "..."}  -> internal token

There is no user table in F4, so the demo uses two shared passwords from the
environment (DEMO_CUSTOMER_PASSWORD, DEMO_INTERNAL_PASSWORD). If a password is
not set, that kind of login is disabled. ADR-010 explains why this is enough
for the project and what would replace it in production.
"""

import hmac
import re

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.common import ErrorResponse
from app.core.config import get_settings
from app.core.security import issue_token

CUSTOMER_CODE = re.compile(r"^CU-[A-Z0-9]{1,27}$")

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    username: str = Field(min_length=1, max_length=30, examples=["CU-MAC000002"])
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="seconds", examples=[3600])


def _matches(given: str, expected: str | None) -> bool:
    return expected is not None and hmac.compare_digest(given.encode(), expected.encode())


@router.post(
    "/token",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse, "description": "Wrong username or password"}},
    summary="Get a JWT for a customer or an internal user",
)
def login(body: TokenRequest):
    settings = get_settings()
    if body.username == "internal" and _matches(body.password, settings.demo_internal_password):
        token = issue_token("internal")
    elif CUSTOMER_CODE.match(body.username) and _matches(body.password, settings.demo_customer_password):
        token = issue_token("customer", customer_code=body.username)
    else:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")
    return TokenResponse(access_token=token, expires_in=settings.jwt_expire_minutes * 60)
