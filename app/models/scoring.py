import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

# Supports PostgreSQL JSONB with graceful fallback to JSON for SQLite/portable testing
JSONType = JSONB().with_variant(JSON(), "sqlite")


class ScoringRequest(Base):
    __tablename__ = "scoring_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    input_features: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    predicted_probability: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # APPROVE, REVIEW, DENY
    model_version: Mapped[str] = mapped_column(
        String(50), ForeignKey("model_versions.version"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Relationships
    user = relationship("User", back_populates="scoring_requests")
    model_version_rel = relationship("ModelVersion", back_populates="scoring_requests")
