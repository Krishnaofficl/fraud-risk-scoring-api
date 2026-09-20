from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.schemas.error import ErrorResponse


def test_error_response_valid():
    err = ErrorResponse(
        error_code="VALIDATION_ERROR",
        message="Payload failed schema validation",
        detail=[{"field": "disbursed_amount", "issue": "Must be greater than 0"}],
        request_id="req_test_12345",
    )
    assert err.error_code == "VALIDATION_ERROR"
    assert err.message == "Payload failed schema validation"
    assert len(err.detail) == 1
    assert err.request_id == "req_test_12345"
    assert isinstance(err.timestamp, datetime)


def test_error_response_defaults():
    err = ErrorResponse(
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected condition occurred",
    )
    assert err.error_code == "INTERNAL_SERVER_ERROR"
    assert err.message == "An unexpected condition occurred"
    assert err.detail is None
    assert err.request_id is None
    assert isinstance(err.timestamp, datetime)
    assert err.timestamp.tzinfo == timezone.utc


def test_error_response_missing_required_fields():
    with pytest.raises(ValidationError):
        ErrorResponse(message="Missing error_code")

    with pytest.raises(ValidationError):
        ErrorResponse(error_code="SOME_ERROR")
