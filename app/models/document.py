from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Document(Base):
    """Uploaded source document attached to a claim.

    A claim may have one document for each supported document type. File
    metadata is stored with the row so later OCR and officer review screens do
    not need to inspect local storage just to display intake status.
    """

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("claim_id", "doc_type", name="uq_documents_claim_doc_type"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(100), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    reference_number: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    uploaded_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    claim = relationship("Claim", back_populates="documents")
    extracted_fields = relationship("ExtractedField", back_populates="document")
    ocr_runs = relationship("OCRRun", back_populates="document")
