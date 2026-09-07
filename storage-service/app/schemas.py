from pydantic import BaseModel, Field, field_validator


class UploadFileMeta(BaseModel):
    """Validates the metadata of an incoming multipart file part before it's read."""

    filename: str
    content_type: str

    @field_validator("content_type")
    @classmethod
    def must_be_image(cls, value: str) -> str:
        if not value.startswith("image/"):
            raise ValueError(f"Unsupported content type: {value!r}; only image/* is allowed")
        return value


class UploadResponse(BaseModel):
    cid: str


class ListingFields(BaseModel):
    """Text fields submitted alongside the image on POST /listing-metadata.
    Limits mirror the frontend form's own validation (defense in depth --
    the backend never trusts client-side validation alone)."""

    description: str = Field(min_length=1, max_length=500)
    location: str = Field(min_length=1, max_length=200)

    @field_validator("description", "location")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class ErrorResponse(BaseModel):
    error: str
