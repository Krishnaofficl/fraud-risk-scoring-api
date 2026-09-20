from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project Metadata
    PROJECT_NAME: str = "Fraud & Risk Scoring API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Database Configuration
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fraud_db"

    # Security & JWT
    JWT_SECRET: str = "change-this-to-a-secure-random-32-byte-secret-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Model Artifacts
    MODEL_PATH: str = "artifacts/model_pipeline.joblib"
    MODEL_VERSION: str = "v1-baseline"

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def assemble_async_db_connection(cls, v: str) -> str:
        """
        Ensures the database connection URL uses the asyncpg driver.
        Cloud hosts (Render, Railway, Fly) often provide 'postgres://' or 'postgresql://'.
        SQLAlchemy async requires 'postgresql+asyncpg://'.
        """
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://") and not v.startswith("postgresql+asyncpg://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


settings = Settings()
