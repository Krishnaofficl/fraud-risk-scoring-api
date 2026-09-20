from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """
    Standardized, uniform error envelope for all client-facing errors across the API.
    Prevents leaking internal stack traces and provides consistent client error handling.
    """
    model_config = ConfigDict(populate_by_name=True)

    error_code: str = Field(
        ...,
        description="Machine-readable error classification code",
        examples=["VALIDATION_ERROR", "AUTHENTICATION_FAILED", "ENTITY_NOT_FOUND", "MODEL_UNAVAILABLE"],
    )
    message: str = Field(
        ...,
        description="Human-readable summary of the error",
        examples=["The submitted request payload contains validation errors."],
    )
    detail: Optional[Any] = Field(
        default=None,
        description="Detailed contextual diagnostic information or list of field validation errors",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Unique request tracing/correlation identifier",
        examples=["req_8f12a93c"],
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the error occurred",
    )
