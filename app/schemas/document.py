from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field


class DocumentRead(BaseModel):
    """API response for an uploaded document."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    doc_type: str
    original_filename: str | None = None
    file_path: str = Field(exclude=True)
    stored_filename: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    uploaded_at: datetime | None
    ocr_status: str = "pending"
    extraction_status: str = "pending"
    verification_status: str = "pending"

    @computed_field
    @property
    def view_url(self) -> str:
        return f"/documents/{self.id}/preview"

    @computed_field
    @property
    def download_url(self) -> str:
        return f"/documents/{self.id}/download"
