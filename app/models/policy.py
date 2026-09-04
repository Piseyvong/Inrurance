from sqlalchemy import Boolean, DateTime, Float, JSON, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InsurancePolicy(Base):
    """Versionable, admin-managed validation requirements for a claim type."""

    __tablename__ = "insurance_policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    claim_type: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    required_documents: Mapped[list] = mapped_column(JSON, nullable=False)
    validation_rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    auto_approval_threshold: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    minimum_ocr_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.80)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
