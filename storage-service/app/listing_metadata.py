from aiohttp import web
from pydantic import ValidationError

from .pinata import PinataUploadError
from .responses import error_response
from .schemas import ListingFields, UploadFileMeta, UploadResponse
from .upload_utils import FileTooLargeError, read_multipart_file

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB, mirrors upload.py's limit


async def listing_metadata_handler(request: web.Request) -> web.Response:
    """POST /listing-metadata: accepts an image (field "file") plus "title",
    "description", and "location" text fields, pins the image to Pinata,
    bundles it with the text fields into a JSON document, pins that JSON
    to Pinata too, and returns the JSON's CID -- this is the CID that goes
    on-chain as LostAndFound.createListing's itemCID, so the contract
    points at a metadata blob rather than just the raw image."""
    config = request.app["config"]
    if not config.pinata_jwt:
        return error_response("Server misconfigured: PINATA_JWT is not set", status=500)

    reader = await request.multipart()

    text_fields = {}
    image_meta = None
    image_bytes = None

    while True:
        field = await reader.next()
        if field is None:
            break

        if field.name == "file":
            try:
                image_meta = UploadFileMeta(
                    filename=field.filename or "upload",
                    content_type=field.headers.get("Content-Type", ""),
                )
            except ValidationError as exc:
                return error_response(str(exc), status=400)

            try:
                image_bytes = await read_multipart_file(field, MAX_FILE_SIZE_BYTES)
            except FileTooLargeError:
                return error_response("File exceeds the 10 MB upload limit", status=413)
        elif field.name in ("title", "description", "location"):
            text_fields[field.name] = await field.text()

    if image_meta is None or not image_bytes:
        return error_response('Expected a multipart field named "file"', status=400)

    try:
        listing_fields = ListingFields(
            title=text_fields.get("title", ""),
            description=text_fields.get("description", ""),
            location=text_fields.get("location", ""),
        )
    except ValidationError as exc:
        return error_response(str(exc), status=400)

    pinata_client = request.app["pinata_client"]
    try:
        image_cid = await pinata_client.upload_file(
            image_bytes, image_meta.filename, image_meta.content_type
        )
        metadata_cid = await pinata_client.upload_json(
            {
                "title": listing_fields.title,
                "description": listing_fields.description,
                "location": listing_fields.location,
                "image": f"ipfs://{image_cid}",
            }
        )
    except PinataUploadError as exc:
        return error_response(f"Failed to upload to Pinata: {exc}", status=502)

    return web.json_response(UploadResponse(cid=metadata_cid).model_dump())
