import uuid
from datetime import timedelta
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete

from app.main import app
from app.db.session import async_session_maker
from app.models.user import User
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_users_me_unauthorized_cases():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Case 1: Missing Authorization header
        resp_no_token = await client.get("/v1/users/me")
        assert resp_no_token.status_code == 401
        assert "Not authenticated" in resp_no_token.json()["detail"]

        # Case 2: Tampered Bearer token
        resp_bad_token = await client.get(
            "/v1/users/me",
            headers={"Authorization": "Bearer malformed.tampered.token"},
        )
        assert resp_bad_token.status_code == 401

        # Case 3: Expired Bearer token
        expired_token = create_access_token(
            data={"sub": str(uuid.uuid4())},
            expires_delta=timedelta(seconds=-10),
        )
        resp_expired = await client.get(
            "/v1/users/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp_expired.status_code == 401


@pytest.mark.asyncio
async def test_full_auth_lifecycle_and_users_me():
    """
    Validates Phase 3 Exit Criteria:
    Can register, log in, receive a valid JWT, and authenticate against /v1/users/me.
    """
    unique_email = f"lifecycle_{uuid.uuid4().hex[:8]}@example.com"
    password = "SuperSecurePassword123!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register
        reg_resp = await client.post(
            "/auth/register",
            json={"email": unique_email, "password": password},
        )
        assert reg_resp.status_code == 201
        created_user = reg_resp.json()
        user_id = created_user["id"]
        assert created_user["email"] == unique_email

        # 2. Login
        login_resp = await client.post(
            "/auth/login",
            json={"email": unique_email, "password": password},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        assert token is not None

        # 3. Authenticate against /v1/users/me
        me_resp = await client.get(
            "/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["id"] == user_id
        assert me_data["email"] == unique_email
        assert me_data["is_active"] is True
        assert "created_at" in me_data
        # Ensure passwords are never present
        assert "password" not in me_data
        assert "hashed_password" not in me_data

        # 4. Clean up test user
        async with async_session_maker() as session:
            await session.execute(delete(User).where(User.id == uuid.UUID(user_id)))
            await session.commit()
