from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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


_STATUS_TO_CODE = {401: "unauthorized", 403: "forbidden", 404: "not_found", 409: "conflict"}


def add_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _http_handler(_: Request, exc: HTTPException) -> JSONResponse:
        status_code = exc.status_code or 500
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=status_code,
            content={"code": _STATUS_TO_CODE.get(status_code, "error"), "message": detail},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"code": "validation_error", "message": str(exc.errors())},
        )
