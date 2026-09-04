"""ORM model for OCR processing history."""

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OCRRun(Base):
    """One OCR attempt for one uploaded document.

    OCR runs are append-only for auditability. A failed attempt remains visible
    instead of overwriting earlier evidence, and later successful retries create
    additional rows.
    """

    __tablename__ = "ocr_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    engine: Mapped[str] = mapped_column(String(100), nullable=False)
    engine_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    average_confidence: Mapped[Numeric] = mapped_column(Numeric(5, 4), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document = relationship("Document", back_populates="ocr_runs")
    extracted_fields = relationship("ExtractedField", back_populates="ocr_run")
