from pydantic import BaseModel, field_validator


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


class ErrorResponse(BaseModel):
    error: str
