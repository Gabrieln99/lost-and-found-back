import aiohttp

PINATA_UPLOAD_URL = "https://api.pinata.cloud/pinning/pinFileToIPFS"


class PinataUploadError(Exception):
    """Raised when Pinata rejects an upload or the request otherwise fails."""


class PinataClient:
    def __init__(self, jwt: str, session: aiohttp.ClientSession) -> None:
        self._jwt = jwt
        self._session = session

    async def upload_file(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        form = aiohttp.FormData()
        form.add_field("file", file_bytes, filename=filename, content_type=content_type)
        headers = {"Authorization": f"Bearer {self._jwt}"}

        try:
            async with self._session.post(
                PINATA_UPLOAD_URL, data=form, headers=headers
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    raise PinataUploadError(
                        f"Pinata responded with status {response.status}: {body}"
                    )
                data = await response.json()
        except aiohttp.ClientError as exc:
            raise PinataUploadError(f"Network error contacting Pinata: {exc}") from exc

        cid = data.get("IpfsHash")
        if not cid:
            raise PinataUploadError("Pinata response did not include an IpfsHash")
        return cid
