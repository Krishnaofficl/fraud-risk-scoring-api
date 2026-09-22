"""
Integration tests for service health, liveness, and readiness probes.
Verifies that GET /health operates independently of downstream infrastructure,
and GET /health/ready performs active dependency checks, gracefully degrading
to HTTP 503 Service Unavailable when the database or model pipeline is unavailable.
"""

from unittest.mock import AsyncMock
import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app, lifespan
from app.schemas.error import ErrorResponse


@pytest.mark.integration
class TestHealthProbes:
    """Validates liveness and dual-readiness health inspection probes."""

    async def test_liveness_probe_always_ok(self, client: AsyncClient):
        """GET /health must return 200 OK without requiring active dependencies."""
        response = await client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"
        assert "project" in data
        assert "environment" in data

    async def test_readiness_probe_healthy_when_dependencies_ready(self, client: AsyncClient):
        """GET /health/ready returns 200 OK when DB and model are fully initialized."""
        response = await client.get("/health/ready")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"
        assert data["model_loaded"] is True
        assert "model_version" in data

    async def test_readiness_probe_degrades_when_model_missing(self):
        """GET /health/ready returns 503 with MODEL_UNAVAILABLE error when pipeline missing."""
        # Simulate uninitialized model pipeline in memory
        saved_pipeline = getattr(app.state, "model_pipeline", None)
        app.state.model_pipeline = None

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                response = await client.get("/health/ready")
                assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
                data = response.json()
                assert data["error_code"] == "MODEL_UNAVAILABLE"
                assert "not loaded in memory" in data["message"]
                ErrorResponse.model_validate(data)
        finally:
            app.state.model_pipeline = saved_pipeline

    async def test_readiness_probe_degrades_when_database_down(self, client: AsyncClient):
        """GET /health/ready returns 503 with DATABASE_UNAVAILABLE when database ping fails."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = ConnectionRefusedError("PostgreSQL server stopped unexpectedly")

        async def override_failing_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_failing_get_db

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as test_client:
                response = await test_client.get("/health/ready")
                assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
                data = response.json()
                assert data["error_code"] == "DATABASE_UNAVAILABLE"
                assert "unreachable or degraded" in data["message"]
                assert "PostgreSQL server stopped unexpectedly" in data["detail"]
                ErrorResponse.model_validate(data)
        finally:
            app.dependency_overrides.pop(get_db, None)
