"""API exception handlers with a consistent response shape."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.models.responses import error_response


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    response = error_response(
        code="http_error",
        message=str(exc.detail),
        request_id=_request_id(request),
    )
    return JSONResponse(status_code=exc.status_code, content=response.model_dump())


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    response = error_response(
        code="validation_error",
        message="The request payload or parameters are invalid.",
        request_id=_request_id(request),
        details={"errors": exc.errors()},
    )
    return JSONResponse(status_code=422, content=response.model_dump())


async def unhandled_exception_handler(request: Request, exc: Exception):
    response = error_response(
        code="internal_error",
        message="The request could not be completed safely.",
        request_id=_request_id(request),
    )
    return JSONResponse(status_code=500, content=response.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
