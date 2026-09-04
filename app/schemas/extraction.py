"""Schemas for structured field extraction from OCR text."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ExtractedValue(BaseModel):
    """One candidate value extracted from OCR text."""

    field_name: str
    field_value: str | None
    confidence: Decimal | None = None
    supporting_line_refs: list[str] = []
    validation_status: str = "unclear"


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
    confidence: Decimal | None
    supporting_line_refs: str | None
    extraction_method: str | None
    validation_status: str | None
    created_at: datetime | None
