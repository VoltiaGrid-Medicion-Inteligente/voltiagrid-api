"""Shared pieces of the three API contracts (US-12, T-12.1).

Authentication (US-13, T-13.1): every protected route needs
`Authorization: Bearer <JWT>`. Get a token from `POST /auth/token` of the
customer consumption API. The token says who the caller is (role and customer
code); the routes never trust a customer code sent by the caller for that.
"""


from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.core.security import InvalidToken, decode_token

T = TypeVar("T")

bearer = HTTPBearer(auto_error=False, description="JWT from POST /auth/token of the customer consumption API")




class FieldError(BaseModel):
    field: str = Field(examples=["acorn_grouped"])
    message: str = Field(examples=["Input should be 'Affluent', 'Comfortable', 'Adversity' or 'Unknown'"])


class ErrorResponse(BaseModel):
    """The one error body every API returns."""

    detail: str = Field(examples=["Transformer 'TR-99999' not found"])
    errors: list[FieldError] | None = Field(default=None, description="Only on 422: one item per invalid field")


class Health(BaseModel):
    status: Literal["ok"] = "ok"


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int = Field(ge=1, examples=[1])
    size: int = Field(ge=1, le=200, examples=[50])
    total: int = Field(ge=0, examples=[200])


@dataclass(frozen=True)
class Principal:
    role: Literal["customer", "internal"]
    customer_code: str | None = None


def get_principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
    """Who is calling. 401 when there is no token or it is not valid."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        claims = decode_token(credentials.credentials)
    except InvalidToken as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    if claims["role"] == "internal":
        return Principal(role="internal")
    return Principal(role="customer", customer_code=claims["sub"])




def require_internal(principal: Principal = Depends(get_principal)) -> Principal:
    """Only internal users (billing, control center, operations). 403 for customers."""
    if principal.role != "internal":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Internal users only")
    return principal


AUTH_ERRORS = {
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired token"},
    403: {"model": ErrorResponse, "description": "The caller is not allowed to read this resource"},
}
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Not found"}}

