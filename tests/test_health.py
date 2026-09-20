import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock
from fastapi import status

from app.main import app, lifespan
from app.db.session import get_db
from app.schemas.error import ErrorResponse


@pytest.mark.asyncio
async def test_liveness_probe():
    """Verify GET /health returns 200 OK without requiring dependencies."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"
        assert "project" in data
        assert "environment" in data


@pytest.mark.asyncio
async def test_readiness_probe_healthy():
    """Verify GET /health/ready returns 200 OK when DB and ML model pipeline are both ready."""
    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/ready")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "ready"
            assert data["database"] == "connected"
            assert data["model_loaded"] is True
            assert "model_version" in data


@pytest.mark.asyncio
async def test_readiness_probe_degraded_model_missing():
    """Verify GET /health/ready returns 503 MODEL_UNAVAILABLE when model_pipeline is not loaded."""
    # Ensure model pipeline is not present in app.state
    app.state.model_pipeline = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["error_code"] == "MODEL_UNAVAILABLE"
        assert "not loaded in memory" in data["message"]
        ErrorResponse.model_validate(data)


@pytest.mark.asyncio
async def test_readiness_probe_degraded_database_down():
    """Verify GET /health/ready returns 503 DATABASE_UNAVAILABLE when database ping fails."""
    async with lifespan(app):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = ConnectionRefusedError("PostgreSQL server stopped unexpectedly")

        async def override_failing_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_failing_get_db

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/health/ready")
                assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
                data = response.json()
                assert data["error_code"] == "DATABASE_UNAVAILABLE"
                assert "unreachable or degraded" in data["message"]
                assert "PostgreSQL server stopped unexpectedly" in data["detail"]
                ErrorResponse.model_validate(data)
        finally:
            app.dependency_overrides.pop(get_db, None)
