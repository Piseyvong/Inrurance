from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentRequirement(BaseModel):
    type: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    title: str
    description: str
    required_fields: list[str] = Field(default_factory=list)


class PolicyWrite(BaseModel):
    claim_type: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    display_name: str
    description: str | None = None
    required_documents: list[DocumentRequirement]
    validation_rules: dict = Field(default_factory=dict)
    auto_approval_threshold: Decimal | None = None
    currency: str = "USD"
    minimum_ocr_confidence: float = Field(default=0.80, ge=0, le=1)
    active: bool = True

    @field_validator("required_documents")
    @classmethod
    def unique_document_types(cls, value):
        types = [item.type for item in value]
        if not value or len(types) != len(set(types)):
            raise ValueError("At least one uniquely typed document is required")
        return value


class PolicyRead(PolicyWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    version: int = 1
