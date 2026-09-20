from typing import Any, Optional
from fastapi import status


class AppException(Exception):
    """Base exception for all domain and service exceptions in the application."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: Optional[Any] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.detail = detail


class DatabaseUnavailableException(AppException):
    """Raised when the PostgreSQL database connection fails, is unreachable, or times out."""

    def __init__(
        self,
        message: str = "Database service is currently unreachable or degraded.",
        detail: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            error_code="DATABASE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )


class ModelNotLoadedException(AppException):
    """Raised when an inference endpoint is requested but the ML model is not in memory."""

    def __init__(
        self,
        message: str = "Machine learning risk scoring pipeline is not loaded in memory.",
        detail: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            error_code="MODEL_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )


class EntityNotFoundException(AppException):
    """Raised when a requested resource (user, scoring record, etc.) does not exist."""

    def __init__(
        self,
        message: str = "Requested entity was not found.",
        detail: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            error_code="ENTITY_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class AuthenticationFailedException(AppException):
    """Raised when user authentication credentials are missing, invalid, or expired."""

    def __init__(
        self,
        message: str = "Could not validate authentication credentials.",
        detail: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_FAILED",
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


class AuthorizationFailedException(AppException):
    """Raised when an authenticated user attempts to access a resource owned by another user."""

    def __init__(
        self,
        message: str = "You do not have permission to access or modify this resource.",
        detail: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_FAILED",
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class ConflictException(AppException):
    """Raised when an entity already exists (e.g. duplicate user registration email)."""

    def __init__(
        self,
        message: str = "A conflict occurred with an existing resource.",
        detail: Optional[Any] = None,
    ):
        super().__init__(
            message=message,
            error_code="RESOURCE_CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )
