import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from app.core.error_handlers import register_exception_handlers
from app.core.exceptions import (
    AppException,
    DatabaseUnavailableException,
    EntityNotFoundException,
    ModelNotLoadedException,
)
from app.schemas.error import ErrorResponse


@pytest.fixture
def error_test_app() -> FastAPI:
    """Fixture to create an isolated FastAPI app with registered error handlers and test routes."""
    test_app = FastAPI()
    register_exception_handlers(test_app)

    class SampleBody(BaseModel):
        name: str
        age: int

    @test_app.get("/trigger/domain-db")
    async def trigger_db_error():
        raise DatabaseUnavailableException(detail="Failed to connect to postgresql pool.")

    @test_app.get("/trigger/domain-model")
    async def trigger_model_error():
        raise ModelNotLoadedException()

    @test_app.get("/trigger/domain-not-found")
    async def trigger_not_found():
        raise EntityNotFoundException(message="Loan application was not found.")

    @test_app.post("/trigger/validation")
    async def trigger_validation(body: SampleBody):
        return {"name": body.name, "age": body.age}

    @test_app.get("/trigger/http-401")
    async def trigger_http_401():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    @test_app.get("/trigger/http-403")
    async def trigger_http_403():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden action",
        )

    @test_app.get("/trigger/unhandled")
    async def trigger_unhandled():
        # Raise unexpected internal error
        raise ZeroDivisionError("Unexpected mathematical singularity")

    return test_app


@pytest.mark.asyncio
async def test_domain_exception_handling(error_test_app: FastAPI):
    """Test that custom domain AppException subclasses produce standardized ErrorResponse JSON."""
    async with AsyncClient(
        transport=ASGITransport(app=error_test_app), base_url="http://test"
    ) as client:
        # 1. DatabaseUnavailableException (503)
        res_db = await client.get("/trigger/domain-db", headers={"X-Request-ID": "req-db-001"})
        assert res_db.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data_db = res_db.json()
        assert data_db["error_code"] == "DATABASE_UNAVAILABLE"
        assert "unreachable or degraded" in data_db["message"]
        assert data_db["detail"] == "Failed to connect to postgresql pool."
        assert data_db["request_id"] == "req-db-001"
        assert "timestamp" in data_db
        # Validate against Pydantic schema
        ErrorResponse.model_validate(data_db)

        # 2. ModelNotLoadedException (503)
        res_model = await client.get("/trigger/domain-model")
        assert res_model.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data_model = res_model.json()
        assert data_model["error_code"] == "MODEL_UNAVAILABLE"
        assert "not loaded in memory" in data_model["message"]
        ErrorResponse.model_validate(data_model)

        # 3. EntityNotFoundException (404)
        res_nf = await client.get("/trigger/domain-not-found")
        assert res_nf.status_code == status.HTTP_404_NOT_FOUND
        data_nf = res_nf.json()
        assert data_nf["error_code"] == "ENTITY_NOT_FOUND"
        assert data_nf["message"] == "Loan application was not found."
        assert data_nf["detail"] == "Loan application was not found."
        ErrorResponse.model_validate(data_nf)


@pytest.mark.asyncio
async def test_validation_error_handling(error_test_app: FastAPI):
    """Test that RequestValidationError produces 422 with VALIDATION_ERROR code and field details."""
    async with AsyncClient(
        transport=ASGITransport(app=error_test_app), base_url="http://test"
    ) as client:
        res = await client.post(
            "/trigger/validation",
            json={"name": "Alice", "age": "not-a-number"},
            headers={"X-Request-ID": "req-val-002"},
        )
        assert res.status_code == 422
        data = res.json()
        assert data["error_code"] == "VALIDATION_ERROR"
        assert data["message"] == "Request payload validation failed."
        assert data["request_id"] == "req-val-002"
        assert isinstance(data["detail"], list)
        assert len(data["detail"]) > 0
        assert data["detail"][0]["loc"] == ["body", "age"]
        ErrorResponse.model_validate(data)


@pytest.mark.asyncio
async def test_http_exception_handling_and_headers(error_test_app: FastAPI):
    """Test standard HTTPException mapping and header preservation."""
    async with AsyncClient(
        transport=ASGITransport(app=error_test_app), base_url="http://test"
    ) as client:
        # Test 401 with headers
        res_401 = await client.get("/trigger/http-401")
        assert res_401.status_code == status.HTTP_401_UNAUTHORIZED
        assert res_401.headers.get("WWW-Authenticate") == "Bearer"
        data_401 = res_401.json()
        assert data_401["error_code"] == "AUTHENTICATION_FAILED"
        assert data_401["message"] == "Token expired"
        assert data_401["detail"] == "Token expired"
        ErrorResponse.model_validate(data_401)

        # Test 403
        res_403 = await client.get("/trigger/http-403")
        assert res_403.status_code == status.HTTP_403_FORBIDDEN
        data_403 = res_403.json()
        assert data_403["error_code"] == "AUTHORIZATION_FAILED"
        assert data_403["message"] == "Forbidden action"
        ErrorResponse.model_validate(data_403)


@pytest.mark.asyncio
async def test_unhandled_exception_sanitization(error_test_app: FastAPI):
    """Test that uncaught exceptions return 500 without leaking stack traces."""
    async with AsyncClient(
        transport=ASGITransport(app=error_test_app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        res = await client.get("/trigger/unhandled")
        assert res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = res.json()
        assert data["error_code"] == "INTERNAL_SERVER_ERROR"
        assert data["message"] == "An unexpected internal server error occurred."
        assert data["detail"] == "Internal server error."
        # Confirm internal exception details are NOT leaked
        assert "ZeroDivisionError" not in str(data)
        assert "singularity" not in str(data)
        ErrorResponse.model_validate(data)
