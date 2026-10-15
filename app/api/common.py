from typing import Annotated, Generic, TypeVar

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

bearer = HTTPBearer(auto_error=False)

class ErrorResponse(BaseModel):
    code: str
    message: str

T = TypeVar("T")

class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int

class Principal(BaseModel):
    kind: str
    customer_code: str | None = None

def get_principal(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Principal:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    token = creds.credentials
    if token == "stub-internal":
        return Principal(kind="internal")
    if token.startswith("stub-customer-"):
        code = token[len("stub-customer-") :]
        if not code:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return Principal(kind="customer", customer_code=code)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

class HealthResponse(BaseModel):
    status: str = "ok"
        