import aiohttp
from aioresponses import aioresponses

import app.upload as upload_module
from app import create_app
from app.pinata import PINATA_UPLOAD_URL

# aioresponses patches ClientSession globally, so without a passthrough it
# also intercepts the test client's own request to the local aiohttp test
# server. Only api.pinata.cloud should actually be mocked.
LOCAL_PASSTHROUGH = ["http://127.0.0.1"]


def mocked_pinata():
    return aioresponses(passthrough=LOCAL_PASSTHROUGH)


async def make_client(aiohttp_client, monkeypatch, pinata_jwt="test-jwt-token"):
    if pinata_jwt is None:
        monkeypatch.delenv("PINATA_JWT", raising=False)
    else:
        monkeypatch.setenv("PINATA_JWT", pinata_jwt)
    app = create_app()
    return await aiohttp_client(app)


def image_form(content=b"fake-image-bytes", filename="pet.png", content_type="image/png"):
    form = aiohttp.FormData()
    form.add_field("file", content, filename=filename, content_type=content_type)
    return form


async def test_upload_success_returns_cid(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata() as mocked:
        mocked.post(PINATA_UPLOAD_URL, payload={"IpfsHash": "bafytestcid123", "PinSize": 10})
        resp = await cli.post("/upload", data=image_form())

    assert resp.status == 200
    body = await resp.json()
    assert body == {"cid": "bafytestcid123"}


async def test_upload_rejects_non_image_content_type(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata():
        resp = await cli.post(
            "/upload",
            data=image_form(
                content=b"%PDF-1.4 fake", filename="doc.pdf", content_type="application/pdf"
            ),
        )

    assert resp.status == 400
    body = await resp.json()
    assert "error" in body


async def test_upload_missing_file_field(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    form = aiohttp.FormData()
    # A filename is needed so aiohttp actually encodes this as
    # multipart/form-data rather than falling back to urlencoded.
    form.add_field("not_a_file", b"whatever", filename="notes.txt", content_type="text/plain")

    with mocked_pinata():
        resp = await cli.post("/upload", data=form)

    assert resp.status == 400


async def test_upload_handles_pinata_failure(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata() as mocked:
        mocked.post(PINATA_UPLOAD_URL, status=500, body="internal error")
        resp = await cli.post("/upload", data=image_form())

    assert resp.status == 502
    body = await resp.json()
    assert "error" in body


async def test_upload_handles_pinata_network_error(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata() as mocked:
        mocked.post(PINATA_UPLOAD_URL, exception=aiohttp.ClientConnectionError("boom"))
        resp = await cli.post("/upload", data=image_form())

    assert resp.status == 502


async def test_upload_rejects_oversized_file(aiohttp_client, monkeypatch):
    monkeypatch.setattr(upload_module, "MAX_FILE_SIZE_BYTES", 10)
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata():
        resp = await cli.post("/upload", data=image_form(content=b"a" * 100))

    assert resp.status == 413


async def test_upload_rejects_when_pinata_jwt_not_configured(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch, pinata_jwt=None)

    with mocked_pinata():
        resp = await cli.post("/upload", data=image_form())

    assert resp.status == 500
