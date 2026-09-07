class FileTooLargeError(Exception):
    """Raised when a streamed multipart file part exceeds the caller's size limit."""


async def read_multipart_file(field, max_size: int) -> bytes:
    """Reads a multipart file part in chunks, aborting once max_size is exceeded
    rather than buffering an arbitrarily large upload into memory first."""
    chunks = []
    total_size = 0
    while True:
        chunk = await field.read_chunk()
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_size:
            raise FileTooLargeError()
        chunks.append(chunk)
    return b"".join(chunks)
