import aiohttp

PINATA_PIN_FILE_URL = "https://api.pinata.cloud/pinning/pinFileToIPFS"
PINATA_PIN_JSON_URL = "https://api.pinata.cloud/pinning/pinJSONToIPFS"

# Backwards-compatible alias; keep existing imports/tests working.
PINATA_UPLOAD_URL = PINATA_PIN_FILE_URL


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

        data = await self._post(PINATA_PIN_FILE_URL, headers=headers, data=form)
        return self._extract_cid(data)

    async def upload_json(self, content: dict) -> str:
        headers = {
            "Authorization": f"Bearer {self._jwt}",
            "Content-Type": "application/json",
        }
        payload = {"pinataContent": content}

        data = await self._post(PINATA_PIN_JSON_URL, headers=headers, json=payload)
        return self._extract_cid(data)

    async def _post(self, url: str, **kwargs) -> dict:
        try:
            async with self._session.post(url, **kwargs) as response:
                if response.status != 200:
                    body = await response.text()
                    raise PinataUploadError(
                        f"Pinata responded with status {response.status}: {body}"
                    )
                return await response.json()
        except aiohttp.ClientError as exc:
            raise PinataUploadError(f"Network error contacting Pinata: {exc}") from exc

    @staticmethod
    def _extract_cid(data: dict) -> str:
        cid = data.get("IpfsHash")
        if not cid:
            raise PinataUploadError("Pinata response did not include an IpfsHash")
        return cid
