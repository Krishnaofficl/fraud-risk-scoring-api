"""
Global Pytest fixtures for integration and unit testing suites.
Configures AsyncClient with FastAPI lifespan, test database session overrides,
transaction rollback isolation, authentication helpers, and event loop connection cleanup.
"""

import uuid
from typing import AsyncGenerator, Dict, Any
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.session import engine, get_db, async_session_maker
from app.main import app, lifespan


@pytest.fixture(autouse=True)
async def clean_db_connections_after_test():
    """
    Ensures connection pool is cleanly disposed between tests, preventing
    closed event loop conflicts with asyncpg on Windows.
    """
    yield
    await engine.dispose()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Asynchronous HTTP test client bound to the FastAPI application.
    Enters lifespan context ensuring ML pipeline, model metadata,
    and background components are fully initialized in memory.
    """
    async with lifespan(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a standalone async database session directly against PostgreSQL.
    """
    async with async_session_maker() as session:
        yield session


@pytest.fixture
async def rollback_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a transaction-isolated database session.
    Overrides FastAPI's get_db dependency so that all database operations
    within the test run inside an outer transaction with savepoints.
    Automatically rolls back on test teardown, leaving the DB in a clean state.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield session

        app.dependency_overrides[get_db] = override_get_db

        try:
            yield session
        finally:
            app.dependency_overrides.pop(get_db, None)
            await transaction.rollback()


@pytest.fixture
async def authenticated_client(client: AsyncClient) -> Dict[str, Any]:
    """
    Convenience fixture providing an authenticated client and valid user session.
    Registers a fresh user, obtains a JWT token, and returns headers and user details.
    """
    unique_email = f"authed_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"

    reg_resp = await client.post(
        "/auth/register",
        json={"email": unique_email, "password": password},
    )
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()

    login_resp = await client.post(
        "/auth/login",
        json={"email": unique_email, "password": password},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "client": client,
        "user": user_data,
        "token": token,
        "headers": headers,
        "email": unique_email,
        "password": password,
    }
