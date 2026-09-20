from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy 2.0 ORM models.
    Provides automated table metadata registration for Alembic migrations.
    """
    pass
