"""Domain errors and the one JSON error format of every API (US-18, T-18.2 and T-18.3).

Services raise domain errors and never build HTTP responses; the handlers
registered here turn every error into the same body:

    {"detail": "Transformer 'TR-99999' not found"}                                     404, 409, 401, 403
    {"detail": "Validation error", "errors": [{"field": "...", "message": "..."}]}     422
    {"detail": "Internal server error"}                                               500 (details only in the log)
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("voltiagrid.api")
LOCATIONS = {"body", "query", "path", "header", "cookie"}


class NotFoundError(Exception):
    """A resource identified by its natural key does not exist."""

    def __init__(self, resource: str, key: str):
        self.resource, self.key = resource, key
        super().__init__(f"{resource} '{key}' not found")


class ConflictError(Exception):
    """The natural key of a new resource already exists."""

    def __init__(self, resource: str, key: str):
        self.resource, self.key = resource, key
        super().__init__(f"{resource} '{key}' already exists")


def _field(loc: tuple) -> str:
    parts = [str(p) for p in loc]
    if parts and parts[0] in LOCATIONS:
        parts = parts[1:]
    return ".".join(parts) or "body"


async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


async def _conflict(_: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{"field": _field(e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "Validation error", "errors": errors})


async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "Internal server error"})


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(NotFoundError, _not_found)
    app.add_exception_handler(ConflictError, _conflict)
    app.add_exception_handler(RequestValidationError, _validation)
    app.add_exception_handler(Exception, _unexpected)
