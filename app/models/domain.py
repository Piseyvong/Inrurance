from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(60))
    role: Mapped[str] = mapped_column(String(30), default="customer")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


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
    updated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


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
    policy_template_id: Mapped[int | None] = mapped_column(ForeignKey("policy_documents.id"), index=True)
    product_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="active")
    start_date: Mapped[Date] = mapped_column(Date)
    end_date: Mapped[Date] = mapped_column(Date)
    coverage_limit: Mapped[float | None] = mapped_column(Numeric(14, 2))
    deductible: Mapped[float | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class PolicyDocument(Base):
    """Versioned policy wording uploaded by an authorized officer."""

    __tablename__ = "policy_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    insurance_product_id: Mapped[int] = mapped_column(ForeignKey("insurance_products.id"), index=True)
    policy_name: Mapped[str] = mapped_column(String(180))
    product_category: Mapped[str] = mapped_column(String(50), index=True)
    policy_code: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[str] = mapped_column(String(50))
    effective_date: Mapped[Date] = mapped_column(Date)
    expiry_date: Mapped[Date | None] = mapped_column(Date)
    language: Mapped[str] = mapped_column(String(30), default="Khmer-English")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_path: Mapped[str] = mapped_column(String(500))
    extracted_text: Mapped[str] = mapped_column(Text)
    required_documents: Mapped[list] = mapped_column(JSON, default=list)
    configured_rules: Mapped[dict] = mapped_column(JSON, default=dict)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PolicyChunk(Base):
    """Searchable, auditable excerpt from one immutable policy document version."""

    __tablename__ = "policy_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    policy_document_id: Mapped[int] = mapped_column(ForeignKey("policy_documents.id", ondelete="CASCADE"), index=True)
    section: Mapped[str | None] = mapped_column(String(255))
    page_number: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class OfficerNote(Base):
    __tablename__ = "officer_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    officer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())


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
