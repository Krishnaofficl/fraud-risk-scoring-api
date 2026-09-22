"""
Integration tests for authentication workflows and user endpoints.
Covers registration, duplicate rejection, password hashing verification,
login flow, credential checking, inactive account blocks, and /v1/users/me.
Runs against the live PostgreSQL database container.
"""

import uuid
from datetime import timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.user import User


@pytest.mark.integration
class TestAuthenticationFlows:
    """End-to-end integration tests for user registration, login, and profile retrieval."""

    async def test_register_success_and_db_state(self, client: AsyncClient, rollback_session):
        """User registers successfully, receives 201, and password is saved as Argon2id hash."""
        email = f"user_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePassword123!"

        payload = {"email": email, "password": password}
        resp = await client.post("/auth/register", json=payload)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"

        body = resp.json()
        assert body["email"] == email
        assert "id" in body
        assert body["is_active"] is True
        assert "password" not in body
        assert "hashed_password" not in body

        # Verify DB entry
        stmt = select(User).where(User.email == email)
        result = await rollback_session.execute(stmt)
        user_db = result.scalar_one_or_none()
        assert user_db is not None
        assert user_db.hashed_password != password
        assert user_db.hashed_password.startswith("$argon2id$")

    async def test_register_duplicate_email_conflict(self, client: AsyncClient, rollback_session):
        """Registering with an already existing email returns 409 Conflict."""
        email = f"duplicate_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePassword123!"
        payload = {"email": email, "password": password}

        first_resp = await client.post("/auth/register", json=payload)
        assert first_resp.status_code == 201

        dup_resp = await client.post("/auth/register", json=payload)
        assert dup_resp.status_code == 409
        assert "already exists" in dup_resp.json()["detail"].lower()

    async def test_register_validation_errors(self, client: AsyncClient):
        """Invalid emails and passwords below 8 chars return 422 Unprocessable Entity."""
        # Invalid email
        resp1 = await client.post(
            "/auth/register",
            json={"email": "invalid-email-address", "password": "SecurePassword123!"},
        )
        assert resp1.status_code == 422

        # Short password
        resp2 = await client.post(
            "/auth/register",
            json={"email": "good@example.com", "password": "short"},
        )
        assert resp2.status_code == 422

    async def test_login_success_and_token_claims(self, client: AsyncClient, rollback_session):
        """Successful login returns bearer token with expiration and valid claims."""
        email = f"login_{uuid.uuid4().hex[:8]}@example.com"
        password = "CorrectPassword123!"

        await client.post("/auth/register", json={"email": email, "password": password})

        login_resp = await client.post("/auth/login", json={"email": email, "password": password})
        assert login_resp.status_code == 200
        token_data = login_resp.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert token_data["expires_in"] == 3600

    async def test_login_invalid_password(self, client: AsyncClient, rollback_session):
        """Invalid password yields 401 Unauthorized without leaking account existence."""
        email = f"badpass_{uuid.uuid4().hex[:8]}@example.com"
        password = "CorrectPassword123!"

        await client.post("/auth/register", json={"email": email, "password": password})

        resp = await client.post("/auth/login", json={"email": email, "password": "WrongPassword999!"})
        assert resp.status_code == 401
        assert "invalid email or password" in resp.json()["detail"].lower()

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Login with non-existent email returns 401 Unauthorized."""
        resp = await client.post(
            "/auth/login",
            json={"email": "nonexistent_ghost@example.com", "password": "SomePassword123!"},
        )
        assert resp.status_code == 401
        assert "invalid email or password" in resp.json()["detail"].lower()

    async def test_login_inactive_user_forbidden(self, client: AsyncClient, rollback_session):
        """Deactivated user account returns 403 Forbidden upon login attempt."""
        email = f"inactive_{uuid.uuid4().hex[:8]}@example.com"
        password = "Password123!"

        reg_resp = await client.post("/auth/register", json={"email": email, "password": password})
        assert reg_resp.status_code == 201
        user_id = uuid.UUID(reg_resp.json()["id"])

        # Deactivate user in DB
        stmt = select(User).where(User.id == user_id)
        result = await rollback_session.execute(stmt)
        user_db = result.scalar_one()
        user_db.is_active = False
        await rollback_session.commit()

        login_resp = await client.post("/auth/login", json={"email": email, "password": password})
        assert login_resp.status_code == 403
        assert "inactive" in login_resp.json()["detail"].lower()

    async def test_users_me_success(self, authenticated_client: dict):
        """Authenticated user successfully accesses /v1/users/me returning profile data."""
        client = authenticated_client["client"]
        headers = authenticated_client["headers"]
        expected_email = authenticated_client["email"]

        resp = await client.get("/v1/users/me", headers=headers)
        assert resp.status_code == 200
        profile = resp.json()
        assert profile["email"] == expected_email
        assert profile["is_active"] is True
        assert "id" in profile
        assert "password" not in profile

    async def test_users_me_unauthorized_cases(self, client: AsyncClient):
        """Verify unauthenticated, malformed, and expired tokens receive 401."""
        # 1. Missing header
        resp1 = await client.get("/v1/users/me")
        assert resp1.status_code == 401

        # 2. Malformed token
        resp2 = await client.get(
            "/v1/users/me",
            headers={"Authorization": "Bearer bad.token.here"},
        )
        assert resp2.status_code == 401

        # 3. Expired token
        expired_jwt = create_access_token(
            data={"sub": str(uuid.uuid4())},
            expires_delta=timedelta(seconds=-30),
        )
        resp3 = await client.get(
            "/v1/users/me",
            headers={"Authorization": f"Bearer {expired_jwt}"},
        )
        assert resp3.status_code == 401


@pytest.mark.integration
class TestGetCurrentUserDependency:
    """Direct tests for get_current_user dependency resolution against database."""

    async def test_get_current_user_valid(self, rollback_session):
        from app.core.security import get_current_user, hash_password

        unique_email = f"dep_{uuid.uuid4().hex[:8]}@example.com"
        user = User(
            email=unique_email,
            hashed_password=hash_password("ValidPassword123!"),
            is_active=True,
        )
        rollback_session.add(user)
        await rollback_session.commit()
        await rollback_session.refresh(user)

        token = create_access_token(data={"sub": str(user.id), "email": unique_email})
        resolved = await get_current_user(token=token, db=rollback_session)
        assert resolved.id == user.id
        assert resolved.email == unique_email
        assert resolved.is_active is True

    async def test_get_current_user_inactive_account(self, rollback_session):
        from fastapi import HTTPException
        from app.core.security import get_current_user, hash_password

        user = User(
            email=f"inactive_dep_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("ValidPassword123!"),
            is_active=False,
        )
        rollback_session.add(user)
        await rollback_session.commit()
        await rollback_session.refresh(user)

        token = create_access_token(data={"sub": str(user.id)})
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token=token, db=rollback_session)
        assert exc.value.status_code == 403
