import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

from app.main import app
from app.db.session import async_session_maker
from app.models.user import User
from app.core.security import decode_access_token


@pytest.mark.asyncio
async def test_login_flow_and_token_validation():
    unique_email = f"login_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "CorrectPassword123!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register the user
        reg_resp = await client.post(
            "/auth/register",
            json={"email": unique_email, "password": password},
        )
        assert reg_resp.status_code == 201
        user_id = reg_resp.json()["id"]

        # 2. Successful Login
        login_resp = await client.post(
            "/auth/login",
            json={"email": unique_email, "password": password},
        )
        assert login_resp.status_code == 200
        token_data = login_resp.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert token_data["expires_in"] == 3600

        # Verify decoded token claims
        decoded = decode_access_token(token_data["access_token"])
        assert decoded["sub"] == user_id
        assert decoded["email"] == unique_email

        # 3. Invalid Password Attempt (401)
        bad_pw_resp = await client.post(
            "/auth/login",
            json={"email": unique_email, "password": "WrongPassword999!"},
        )
        assert bad_pw_resp.status_code == 401
        assert "Invalid email or password" in bad_pw_resp.json()["detail"]

        # 4. Non-Existent Email (401)
        non_existent_resp = await client.post(
            "/auth/login",
            json={"email": "nonexistent_ghost_user@example.com", "password": password},
        )
        assert non_existent_resp.status_code == 401

        # 5. Inactive User (403)
        async with async_session_maker() as session:
            stmt = select(User).where(User.email == unique_email)
            result = await session.execute(stmt)
            db_user = result.scalar_one()
            db_user.is_active = False
            await session.commit()

        inactive_resp = await client.post(
            "/auth/login",
            json={"email": unique_email, "password": password},
        )
        assert inactive_resp.status_code == 403
        assert "inactive" in inactive_resp.json()["detail"]

        # Clean up test user
        async with async_session_maker() as session:
            await session.execute(delete(User).where(User.email == unique_email))
            await session.commit()
