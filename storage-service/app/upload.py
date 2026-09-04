from aiohttp import web
from pydantic import ValidationError

from .pinata import PinataUploadError
from .schemas import ErrorResponse, UploadFileMeta, UploadResponse

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def error_response(message: str, status: int) -> web.Response:
    return web.json_response(ErrorResponse(error=message).model_dump(), status=status)


async def upload_handler(request: web.Request) -> web.Response:
    config = request.app["config"]
    if not config.pinata_jwt:
        return error_response("Server misconfigured: PINATA_JWT is not set", status=500)

    reader = await request.multipart()
    field = await reader.next()
    if field is None or field.name != "file":
        return error_response('Expected a multipart field named "file"', status=400)

    try:
        meta = UploadFileMeta(
            filename=field.filename or "upload",
            content_type=field.headers.get("Content-Type", ""),
        )
    except ValidationError as exc:
        return error_response(str(exc), status=400)

    chunks = []
    total_size = 0
    while True:
        chunk = await field.read_chunk()
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > MAX_FILE_SIZE_BYTES:
            return error_response("File exceeds the 10 MB upload limit", status=413)
        chunks.append(chunk)

    file_bytes = b"".join(chunks)
    if not file_bytes:
        return error_response("Uploaded file is empty", status=400)

    pinata_client = request.app["pinata_client"]
    try:
        cid = await pinata_client.upload_file(file_bytes, meta.filename, meta.content_type)
    except PinataUploadError as exc:
        return error_response(f"Failed to upload to Pinata: {exc}", status=502)

    return web.json_response(UploadResponse(cid=cid).model_dump())
