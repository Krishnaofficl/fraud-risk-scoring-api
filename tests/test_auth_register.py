import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

from app.main import app
from app.db.session import async_session_maker
from app.models.user import User


@pytest.mark.asyncio
async def test_register_success_and_conflict():
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    password = "SuperStrongPassword123!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Successful Registration
        payload = {"email": unique_email, "password": password}
        response = await client.post("/auth/register", json=payload)
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["email"] == unique_email
        assert "id" in data
        assert data["is_active"] is True
        assert "created_at" in data
        # Ensure password is NEVER leaked in public response
        assert "password" not in data
        assert "hashed_password" not in data

        user_id = data["id"]

        # 2. Database verification: password stored as Argon2id hash
        async with async_session_maker() as session:
            stmt = select(User).where(User.email == unique_email)
            result = await session.execute(stmt)
            db_user = result.scalar_one_or_none()
            assert db_user is not None
            assert db_user.hashed_password != password
            assert db_user.hashed_password.startswith("$argon2id$")

        # 3. Duplicate Email Registration Conflict (409)
        duplicate_response = await client.post("/auth/register", json=payload)
        assert duplicate_response.status_code == 409
        assert "already exists" in duplicate_response.json()["detail"]

        # 4. Clean up test user
        async with async_session_maker() as session:
            await session.execute(delete(User).where(User.email == unique_email))
            await session.commit()


@pytest.mark.asyncio
async def test_register_validation_errors():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Invalid email format
        bad_email_resp = await client.post(
            "/auth/register",
            json={"email": "not-a-valid-email", "password": "ValidPassword123!"},
        )
        assert bad_email_resp.status_code == 422

        # Password too short (< 8 chars)
        short_pw_resp = await client.post(
            "/auth/register",
            json={"email": "good@example.com", "password": "short"},
        )
        assert short_pw_resp.status_code == 422
