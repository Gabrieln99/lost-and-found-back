from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    location: str = Field(min_length=1, max_length=200)

    @field_validator("title", "description", "location")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class ErrorResponse(BaseModel):
    error: str


class MessageIn(BaseModel):
    """POST body for submitting a signed owner<->finder chat message.
    listingId deliberately isn't a field here -- it comes from the URL
    path, which is what the signature is verified against, so it can't be
    spoofed independently of the endpoint being authorized for."""

    timestamp: int
    body: str = Field(min_length=1, max_length=2000)
    signature: str = Field(min_length=1)

    @field_validator("body")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class MessageOut(BaseModel):
    """A stored message, serialized with by_alias=True so the JSON uses
    listingId (camelCase, matching the rest of this project's on-chain
    field naming) while the Python side stays snake_case."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    listing_id: int = Field(alias="listingId")
    sender: str
    body: str
    timestamp: int


class MessageListResponse(BaseModel):
    messages: list[MessageOut]
