"""Schemas for structured field extraction from OCR text."""

from datetime import datetime
from decimal import Decimal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class ExtractedValue(BaseModel):
    """One candidate value extracted from OCR text."""

    field_name: str
    field_value: str | None = Field(validation_alias=AliasChoices("field_value", "value"))
    normalized_value: str | None = None
    original_ocr_value: str | None = None
    confidence: Decimal | None = None
    supporting_line_refs: list[str] = Field(default_factory=list, validation_alias=AliasChoices("supporting_line_refs", "source_lines"))
    source_text: str | None = None
    semantic_reason: str | None = None
    validation_status: str = "UNCLEAR"

    @field_validator("validation_status", mode="before")
    @classmethod
    def normalize_status(cls, value: object) -> str:
        normalized = str(value or "UNCLEAR").strip().upper()
        return normalized if normalized in {"VALID", "MISSING", "UNCLEAR", "NOT_APPLICABLE", "CONFLICTING"} else "UNCLEAR"


class ExtractionPayload(BaseModel):
    """Validated structured extraction output."""

    values: list[ExtractedValue]


class ExtractedFieldRead(BaseModel):
    """API response for a stored extracted field."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    ocr_run_id: int | None
    field_name: str
    field_value: str | None
    normalized_value: str | None = None
    original_ocr_value: str | None = None
    confidence: Decimal | None
    supporting_line_refs: str | None
    source_text: str | None = None
    semantic_reason: str | None = None
    extraction_method: str | None
    validation_status: str | None
    created_at: datetime | None
    officer_corrected_value: str | None = None
    officer_corrected_by: int | None = None
    officer_corrected_at: datetime | None = None
