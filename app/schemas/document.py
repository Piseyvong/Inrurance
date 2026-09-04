from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    """API response for an uploaded document."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    doc_type: str
    original_filename: str | None = None
    file_path: str
    mime_type: str | None = None
    file_size: int | None = None
    uploaded_at: datetime | None
