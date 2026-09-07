import aiohttp
from aioresponses import aioresponses

from app import create_app
from app.pinata import PINATA_PIN_FILE_URL, PINATA_PIN_JSON_URL

LOCAL_PASSTHROUGH = ["http://127.0.0.1"]


def mocked_pinata():
    return aioresponses(passthrough=LOCAL_PASSTHROUGH)


async def make_client(aiohttp_client, monkeypatch, cors_origin=None):
    monkeypatch.setenv("PINATA_JWT", "test-jwt-token")
    if cors_origin is None:
        monkeypatch.delenv("CORS_ALLOWED_ORIGIN", raising=False)
    else:
        monkeypatch.setenv("CORS_ALLOWED_ORIGIN", cors_origin)
    app = create_app()
    return await aiohttp_client(app)


def image_form(content=b"fake-image-bytes", filename="pet.png", content_type="image/png"):
    form = aiohttp.FormData()
    form.add_field("file", content, filename=filename, content_type=content_type)
    return form


def listing_form(title="Lost cat", description="Lost cat", location="Central Park"):
    form = image_form()
    form.add_field("title", title)
    form.add_field("description", description)
    form.add_field("location", location)
    return form


async def test_upload_response_has_default_cors_header(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata() as mocked:
        mocked.post(PINATA_PIN_FILE_URL, payload={"IpfsHash": "bafytestcid"})
        resp = await cli.post("/upload", data=image_form())

    assert resp.status == 200
    assert resp.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"


async def test_listing_metadata_response_has_cors_header(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata() as mocked:
        mocked.post(PINATA_PIN_FILE_URL, payload={"IpfsHash": "bafyimagecid"})
        mocked.post(PINATA_PIN_JSON_URL, payload={"IpfsHash": "bafymetadatacid"})
        resp = await cli.post("/listing-metadata", data=listing_form())

    assert resp.status == 200
    assert resp.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"


async def test_cors_header_reflects_configured_origin(aiohttp_client, monkeypatch):
    cli = await make_client(
        aiohttp_client, monkeypatch, cors_origin="https://example-app.netlify.app"
    )

    with mocked_pinata() as mocked:
        mocked.post(PINATA_PIN_FILE_URL, payload={"IpfsHash": "bafytestcid"})
        resp = await cli.post("/upload", data=image_form())

    assert resp.headers["Access-Control-Allow-Origin"] == "https://example-app.netlify.app"


async def test_cors_header_present_on_error_responses(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata():
        resp = await cli.post(
            "/upload",
            data=image_form(
                content=b"fake bytes", filename="doc.pdf", content_type="application/pdf"
            ),
        )

    assert resp.status == 400
    assert resp.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"


async def test_preflight_options_request_is_answered_with_cors_headers(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    resp = await cli.options("/listing-metadata")

    assert resp.status == 200
    assert resp.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "POST" in resp.headers["Access-Control-Allow-Methods"]
