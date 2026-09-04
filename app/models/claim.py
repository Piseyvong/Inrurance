from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Claim(Base):
    """Insurance claim intake record.

    The claim status tracks workflow state only. It must not be interpreted as
    an AI approval or rejection decision.
    """

    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    customer_policy_id: Mapped[int | None] = mapped_column(ForeignKey("policies.id"), nullable=True, index=True)
    insurance_product_id: Mapped[int | None] = mapped_column(ForeignKey("insurance_products.id"), nullable=True)
    claimant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    policy_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    claim_type: Mapped[str] = mapped_column(String(50), nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    incident_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    claimed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="submitted")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_band: Mapped[str | None] = mapped_column(String(30), nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    documents = relationship("Document", back_populates="claim")
    rule_results = relationship("RuleResult", back_populates="claim")
    audit_logs = relationship("AuditLog", back_populates="claim")
