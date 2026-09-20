import pytest
from app.db.session import engine


@pytest.fixture(autouse=True)
async def clean_db_connections_after_test():
    """
    Ensures connection pool is cleanly disposed between tests, preventing
    closed event loop conflicts with asyncpg on Windows.
    """
    yield
    await engine.dispose()
