"""Pydantic schemas for OCR processing API responses."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OCRLine(BaseModel):
    """One recognised OCR line with optional evidence metadata."""

    line_id: str
    text: str
    page_number: int | None = None
    confidence: float | None = None
    bounding_box: list[float] | None = None


class OCRRunRead(BaseModel):
    """API response for an OCR processing attempt."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    engine: str
    engine_version: str | None
    status: str
    raw_text: str | None
    result_json: str | None
    average_confidence: Decimal | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
