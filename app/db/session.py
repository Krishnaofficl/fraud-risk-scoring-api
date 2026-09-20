from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings

# Create async engine with connection pooling and asyncpg driver
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True for verbose SQL query logging in development
    future=True,
    pool_pre_ping=True,  # Proactively verifies connections are alive before using them
)

# Async session factory
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an independent, scoped async database session.
    Automatically handles rollbacks on unhandled errors and closes the session.
    """
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
