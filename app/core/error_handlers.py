import logging
from typing import Any, Optional
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.schemas.error import ErrorResponse

logger = get_logger("app.core.error_handlers")

STATUS_TO_ERROR_CODE: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "AUTHENTICATION_FAILED",
    403: "AUTHORIZATION_FAILED",
    404: "ENTITY_NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    408: "REQUEST_TIMEOUT",
    409: "RESOURCE_CONFLICT",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_SERVER_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


from asgi_correlation_id import correlation_id


def _extract_request_id(request: Request) -> Optional[str]:
    """Extract correlation or request ID from contextvar, headers, or request state."""
    cid = correlation_id.get()
    if cid:
        return cid
    req_id = request.headers.get("X-Request-ID")
    if req_id:
        return req_id
    if hasattr(request.state, "request_id"):
        return getattr(request.state, "request_id")
    return None


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Handles all domain and application-specific exceptions derived from AppException.
    Produces a standardized ErrorResponse envelope.
    """
    logger.warning(
        "app_domain_exception",
        error_code=exc.error_code,
        status_code=exc.status_code,
        http_method=request.method,
        path=request.url.path,
        message=exc.message,
    )
    request_id = _extract_request_id(request)
    error_payload = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        detail=exc.detail if exc.detail is not None else exc.message,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload.model_dump(mode="json"),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handles Pydantic request body and query parameter validation errors (422).
    Standardizes the error structure while preserving field-level validation details.
    """
    logger.info(
        "request_validation_failed",
        http_method=request.method,
        path=request.url.path,
        errors_count=len(exc.errors()),
    )
    request_id = _extract_request_id(request)
    encoded_errors = jsonable_encoder(exc.errors())
    error_payload = ErrorResponse(
        error_code="VALIDATION_ERROR",
        message="Request payload validation failed.",
        detail=encoded_errors,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
        content=error_payload.model_dump(mode="json"),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handles HTTP exceptions (from Starlette or FastAPI).
    Translates HTTP status codes into uniform ErrorResponse models while preserving headers.
    """
    request_id = _extract_request_id(request)
    error_code = STATUS_TO_ERROR_CODE.get(exc.status_code, "HTTP_ERROR")

    if isinstance(exc.detail, str):
        message = exc.detail
    elif isinstance(exc.detail, dict) and "message" in exc.detail:
        message = str(exc.detail["message"])
    else:
        message = error_code.replace("_", " ").title()

    error_payload = ErrorResponse(
        error_code=error_code,
        message=message,
        detail=exc.detail,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload.model_dump(mode="json"),
        headers=getattr(exc, "headers", None),
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Catches all unexpected exceptions (500) to prevent leaking raw tracebacks
    or sensitive system internals to clients.
    """
    logger.error(
        "unhandled_system_exception",
        http_method=request.method,
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    request_id = _extract_request_id(request)
    error_payload = ErrorResponse(
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected internal server error occurred.",
        detail="Internal server error.",
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_payload.model_dump(mode="json"),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Registers all custom exception handlers on the FastAPI application instance.
    """
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
