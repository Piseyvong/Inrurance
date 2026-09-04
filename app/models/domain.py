from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="customer")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InsuranceProduct(Base):
    __tablename__ = "insurance_products"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_product_code_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(180))
    product_type: Mapped[str] = mapped_column(String(50), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str | None] = mapped_column(Text)
    policy_document_path: Mapped[str | None] = mapped_column(String(500))
    policy_document_version: Mapped[str | None] = mapped_column(String(50))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[Date | None] = mapped_column(Date)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PolicyRule(Base):
    __tablename__ = "policy_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    insurance_product_id: Mapped[int] = mapped_column(ForeignKey("insurance_products.id", ondelete="CASCADE"), index=True)
    rule_type: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(180))
    configuration: Mapped[dict] = mapped_column(JSON, default=dict)
    clause_reference: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="confirmed")


class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    policy_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    insurance_product_id: Mapped[int] = mapped_column(ForeignKey("insurance_products.id"), index=True)
    product_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="active")
    start_date: Mapped[Date] = mapped_column(Date)
    end_date: Mapped[Date] = mapped_column(Date)


class ClaimCheck(Base):
    __tablename__ = "claim_checks"
    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    check_name: Mapped[str] = mapped_column(String(120))
    outcome: Mapped[str] = mapped_column(String(30))
    score: Mapped[int | None] = mapped_column(Integer)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    outcome: Mapped[str] = mapped_column(String(50), index=True)
    recommended_amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    rationale: Mapped[str] = mapped_column(Text)
    authority: Mapped[str] = mapped_column(String(30), default="rules_engine")
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    final: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConsultationRequest(Base):
    __tablename__ = "consultation_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(60))
    product_interest: Mapped[str | None] = mapped_column(String(180))
    preferred_time: Mapped[str | None] = mapped_column(String(180))
    question: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="new", index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
