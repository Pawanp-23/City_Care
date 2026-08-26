from pydantic import BaseModel, ConfigDict, Field, field_validator


class PrescriptionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    diagnosis: str = Field(min_length=2, max_length=1000)
    medicines: list[str] = Field(default_factory=list, max_length=30)
    instructions: str = Field(min_length=2, max_length=4000)

    @field_validator("medicines")
    @classmethod
    def clean_medicines(cls, values: list[str]) -> list[str]:
        cleaned = [" ".join(item.split()) for item in values if item.strip()]
        if len(cleaned) != len(set(value.casefold() for value in cleaned)):
            raise ValueError("Medicines cannot contain duplicates")
        return cleaned


class PrescriptionAttachmentRequest(BaseModel):
    """JSON transport avoids a hard runtime dependency on python-multipart."""
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=180)
    content_base64: str = Field(min_length=1, max_length=14_000_000)
