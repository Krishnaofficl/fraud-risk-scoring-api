from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ModelVersion(Base):
    __tablename__ = "model_versions"

    version: Mapped[str] = mapped_column(String(50), primary_key=True)
    trained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    reported_auc: Mapped[float] = mapped_column(Float, nullable=False)
    paper_baseline_auc: Mapped[float] = mapped_column(Float, nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    scoring_requests = relationship("ScoringRequest", back_populates="model_version_rel")
