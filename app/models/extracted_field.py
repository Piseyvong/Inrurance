from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExtractedField(Base):
    """Structured value extracted from OCR text.

    LLM or local demo extraction writes candidate values here, but these rows
    are never claim decisions. Verification treats them as untrusted evidence
    that must be validated and compared deterministically.
    """

    __tablename__ = "extracted_fields"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    ocr_run_id: Mapped[int | None] = mapped_column(ForeignKey("ocr_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Numeric] = mapped_column(Numeric(5, 4), nullable=True)
    supporting_line_refs: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    validation_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="extracted_fields")
    ocr_run = relationship("OCRRun", back_populates="extracted_fields")
