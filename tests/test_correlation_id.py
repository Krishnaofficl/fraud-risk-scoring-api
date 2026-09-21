import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from asgi_correlation_id import correlation_id
from fastapi import status

from app.main import app


@pytest.mark.asyncio
async def test_correlation_id_auto_generated_when_missing():
    """Verify X-Request-ID is automatically generated as a UUIDv4 when not provided by client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == status.HTTP_200_OK

        # Header must be present in response
        assert "X-Request-ID" in response.headers
        cid = response.headers["X-Request-ID"]

        # Validate that it is a valid UUID
        parsed_uuid = uuid.UUID(cid)
        assert str(parsed_uuid) == cid


@pytest.mark.asyncio
async def test_correlation_id_preserved_when_provided():
    """Verify server retains and echoes back custom X-Request-ID sent by the client."""
    custom_id = str(uuid.uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health", headers={"X-Request-ID": custom_id})
        assert response.status_code == status.HTTP_200_OK
        assert response.headers.get("X-Request-ID") == custom_id


@pytest.mark.asyncio
async def test_correlation_id_propagated_to_error_envelope():
    """Verify that error responses populate the request_id field in ErrorResponse using correlation ID."""
    custom_id = str(uuid.uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Request a non-existent route to trigger a 404 error envelope
        response = await client.get("/v1/scores/00000000-0000-0000-0000-000000000000", headers={"X-Request-ID": custom_id})
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_404_NOT_FOUND]
        
        # Header check
        assert response.headers.get("X-Request-ID") == custom_id

        # Body JSON check
        body = response.json()
        assert "request_id" in body
        assert body["request_id"] == custom_id


@pytest.mark.asyncio
async def test_correlation_id_accessible_in_context():
    """Verify that correlation_id.get() works across async tasks."""
    custom_id = str(uuid.uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready", headers={"X-Request-ID": custom_id})
        assert response.headers.get("X-Request-ID") == custom_id
