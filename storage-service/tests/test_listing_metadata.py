import aiohttp
from aioresponses import aioresponses

import app.listing_metadata as listing_metadata_module
from app import create_app
from app.pinata import PINATA_PIN_FILE_URL, PINATA_PIN_JSON_URL

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


def listing_form(
    content=b"fake-image-bytes",
    filename="pet.png",
    content_type="image/png",
    title="Lost cat",
    description="Lost cat, orange tabby",
    location="Central Park",
):
    form = aiohttp.FormData()
    form.add_field("file", content, filename=filename, content_type=content_type)
    if title is not None:
        form.add_field("title", title)
    if description is not None:
        form.add_field("description", description)
    if location is not None:
        form.add_field("location", location)
    return form


async def test_listing_metadata_success_returns_metadata_cid(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata() as mocked:
        mocked.post(PINATA_PIN_FILE_URL, payload={"IpfsHash": "bafyimagecid"})
        mocked.post(PINATA_PIN_JSON_URL, payload={"IpfsHash": "bafymetadatacid"})

        resp = await cli.post("/listing-metadata", data=listing_form())

    assert resp.status == 200
    body = await resp.json()
    assert body == {"cid": "bafymetadatacid"}


async def test_listing_metadata_pins_json_with_image_and_text_fields(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata() as mocked:
        mocked.post(PINATA_PIN_FILE_URL, payload={"IpfsHash": "bafyimagecid"})
        mocked.post(PINATA_PIN_JSON_URL, payload={"IpfsHash": "bafymetadatacid"})

        await cli.post(
            "/listing-metadata",
            data=listing_form(title="Lost dog!", description="Lost dog", location="5th Ave"),
        )

        # Inspect the actual pinJSONToIPFS request body via aioresponses' recorded calls.
        recorded = [
            call
            for (method, url), calls in mocked.requests.items()
            if method == "POST" and str(url) == PINATA_PIN_JSON_URL
            for call in calls
        ]
        assert len(recorded) == 1
        sent_payload = recorded[0].kwargs["json"]
        assert sent_payload == {
            "pinataContent": {
                "title": "Lost dog!",
                "description": "Lost dog",
                "location": "5th Ave",
                "image": "ipfs://bafyimagecid",
            }
        }


async def test_listing_metadata_rejects_missing_title(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata():
        resp = await cli.post("/listing-metadata", data=listing_form(title=None))

    assert resp.status == 400


async def test_listing_metadata_rejects_blank_title(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata():
        resp = await cli.post("/listing-metadata", data=listing_form(title="   "))

    assert resp.status == 400


async def test_listing_metadata_rejects_missing_description(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata():
        resp = await cli.post("/listing-metadata", data=listing_form(description=None))

    assert resp.status == 400


async def test_listing_metadata_rejects_missing_location(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata():
        resp = await cli.post("/listing-metadata", data=listing_form(location=None))

    assert resp.status == 400


async def test_listing_metadata_rejects_blank_description(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata():
        resp = await cli.post("/listing-metadata", data=listing_form(description="   "))

    assert resp.status == 400


async def test_listing_metadata_rejects_non_image_content_type(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata():
        resp = await cli.post(
            "/listing-metadata",
            data=listing_form(
                content=b"%PDF fake", filename="doc.pdf", content_type="application/pdf"
            ),
        )

    assert resp.status == 400


async def test_listing_metadata_rejects_missing_file_field(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    form = aiohttp.FormData()
    form.add_field("description", "Lost cat")
    form.add_field("location", "Central Park")
    # No "file" field at all -- needs a filename somewhere to force real
    # multipart encoding rather than aiohttp's urlencoded fallback.
    form.add_field("not_a_file", b"x", filename="x.txt", content_type="text/plain")

    with mocked_pinata():
        resp = await cli.post("/listing-metadata", data=form)

    assert resp.status == 400


async def test_listing_metadata_rejects_oversized_file(aiohttp_client, monkeypatch):
    monkeypatch.setattr(listing_metadata_module, "MAX_FILE_SIZE_BYTES", 10)
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata():
        resp = await cli.post("/listing-metadata", data=listing_form(content=b"a" * 100))

    assert resp.status == 413


async def test_listing_metadata_handles_image_pin_failure(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata() as mocked:
        mocked.post(PINATA_PIN_FILE_URL, status=500, body="internal error")
        resp = await cli.post("/listing-metadata", data=listing_form())

    assert resp.status == 502


async def test_listing_metadata_handles_json_pin_failure(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch)

    with mocked_pinata() as mocked:
        mocked.post(PINATA_PIN_FILE_URL, payload={"IpfsHash": "bafyimagecid"})
        mocked.post(PINATA_PIN_JSON_URL, status=500, body="internal error")
        resp = await cli.post("/listing-metadata", data=listing_form())

    assert resp.status == 502


async def test_listing_metadata_rejects_when_pinata_jwt_not_configured(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch, pinata_jwt=None)

    with mocked_pinata():
        resp = await cli.post("/listing-metadata", data=listing_form())

    assert resp.status == 500
