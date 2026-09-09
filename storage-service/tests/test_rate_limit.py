import time

import aiohttp
from aioresponses import aioresponses
from eth_account import Account
from eth_account.messages import encode_defunct

from app import create_app
from app.pinata import PINATA_PIN_FILE_URL, PINATA_PIN_JSON_URL
from app.signing import build_read_signable_message, build_signable_message

LOCAL_PASSTHROUGH = ["http://127.0.0.1"]

SENDER = Account.create()


def mocked_pinata():
    return aioresponses(passthrough=LOCAL_PASSTHROUGH)


def sign_text(text: str, private_key) -> str:
    signed = Account.sign_message(encode_defunct(text=text), private_key=private_key)
    sig_hex = signed.signature.hex()
    return sig_hex if sig_hex.startswith("0x") else f"0x{sig_hex}"


async def make_client(aiohttp_client, monkeypatch, requests_per_minute=None):
    monkeypatch.setenv("PINATA_JWT", "test-jwt-token")
    monkeypatch.setenv("SEPOLIA_RPC_URL", "http://rpc.example")
    # MESSAGES_DB_PATH defaults to ":memory:" via conftest.py's autouse fixture.
    if requests_per_minute is None:
        monkeypatch.delenv("RATE_LIMIT_REQUESTS_PER_MINUTE", raising=False)
    else:
        monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_MINUTE", str(requests_per_minute))
    app = create_app()
    cli = await aiohttp_client(app)

    async def fake_get_listing_parties(_listing_id):
        return SENDER.address, "0x0000000000000000000000000000000000000000"

    cli.app["contract_reader"].get_listing_parties = fake_get_listing_parties
    return cli


def message_body(listing_id, timestamp, text):
    message = build_signable_message(listing_id, timestamp, text)
    return {"timestamp": timestamp, "body": text, "signature": sign_text(message, SENDER.key)}


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


async def test_requests_within_the_limit_all_succeed(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch, requests_per_minute=3)

    with mocked_pinata() as mocked:
        mocked.post(PINATA_PIN_FILE_URL, payload={"IpfsHash": "bafytestcid"}, repeat=True)

        for _ in range(3):
            resp = await cli.post("/upload", data=image_form())
            assert resp.status == 200


async def test_exceeding_the_limit_returns_429_with_a_clear_error(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch, requests_per_minute=3)

    with mocked_pinata() as mocked:
        mocked.post(PINATA_PIN_FILE_URL, payload={"IpfsHash": "bafytestcid"}, repeat=True)

        for _ in range(3):
            resp = await cli.post("/upload", data=image_form())
            assert resp.status == 200

        resp = await cli.post("/upload", data=image_form())

    assert resp.status == 429
    body = await resp.json()
    assert "error" in body
    assert "rate limit" in body["error"].lower()


async def test_limit_is_shared_across_both_upload_endpoints(aiohttp_client, monkeypatch):
    # Both endpoints burn the same Pinata quota, so a client can't dodge the
    # limit by alternating between them.
    cli = await make_client(aiohttp_client, monkeypatch, requests_per_minute=2)

    with mocked_pinata() as mocked:
        mocked.post(PINATA_PIN_FILE_URL, payload={"IpfsHash": "bafyimagecid"}, repeat=True)
        mocked.post(PINATA_PIN_JSON_URL, payload={"IpfsHash": "bafymetadatacid"}, repeat=True)

        resp1 = await cli.post("/upload", data=image_form())
        resp2 = await cli.post("/listing-metadata", data=listing_form())
        resp3 = await cli.post("/upload", data=image_form())

    assert resp1.status == 200
    assert resp2.status == 200
    assert resp3.status == 429


async def test_rejected_requests_still_carry_the_cors_header(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch, requests_per_minute=1)

    with mocked_pinata() as mocked:
        mocked.post(PINATA_PIN_FILE_URL, payload={"IpfsHash": "bafytestcid"})

        await cli.post("/upload", data=image_form())
        resp = await cli.post("/upload", data=image_form())

    assert resp.status == 429
    assert resp.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"


async def test_a_different_client_ip_gets_its_own_limit(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch, requests_per_minute=1)

    with mocked_pinata() as mocked:
        mocked.post(PINATA_PIN_FILE_URL, payload={"IpfsHash": "bafytestcid"}, repeat=True)

        resp1 = await cli.post("/upload", data=image_form(), headers={"X-Forwarded-For": "1.2.3.4"})
        resp2 = await cli.post("/upload", data=image_form(), headers={"X-Forwarded-For": "5.6.7.8"})
        resp3 = await cli.post(
            "/upload", data=image_form(), headers={"X-Forwarded-For": "1.2.3.4"}
        )

    assert resp1.status == 200
    assert resp2.status == 200  # different client, unaffected by the first one's limit
    assert resp3.status == 429  # same client as resp1, already at its limit


async def test_zero_disables_rate_limiting(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch, requests_per_minute=0)

    with mocked_pinata() as mocked:
        mocked.post(PINATA_PIN_FILE_URL, payload={"IpfsHash": "bafytestcid"}, repeat=True)

        for _ in range(5):
            resp = await cli.post("/upload", data=image_form())
            assert resp.status == 200


async def test_preflight_requests_are_never_rate_limited(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch, requests_per_minute=1)

    for _ in range(5):
        resp = await cli.options("/upload")
        assert resp.status == 200


async def test_sending_messages_is_rate_limited(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch, requests_per_minute=2)
    now = int(time.time())

    resp1 = await cli.post("/listings/3/messages", json=message_body(3, now, "one"))
    resp2 = await cli.post("/listings/3/messages", json=message_body(3, now + 1, "two"))
    resp3 = await cli.post("/listings/3/messages", json=message_body(3, now + 2, "three"))

    assert resp1.status == 201
    assert resp2.status == 201
    assert resp3.status == 429


async def test_message_sending_shares_the_limit_with_uploads(aiohttp_client, monkeypatch):
    # Different endpoints, same abuse-prevention budget -- a client can't
    # dodge the limit by alternating between uploading and messaging.
    cli = await make_client(aiohttp_client, monkeypatch, requests_per_minute=1)
    now = int(time.time())

    with mocked_pinata() as mocked:
        mocked.post(PINATA_PIN_FILE_URL, payload={"IpfsHash": "bafytestcid"})
        resp1 = await cli.post("/upload", data=image_form())

    resp2 = await cli.post("/listings/3/messages", json=message_body(3, now, "hello"))

    assert resp1.status == 200
    assert resp2.status == 429


async def test_reading_messages_is_never_rate_limited(aiohttp_client, monkeypatch):
    cli = await make_client(aiohttp_client, monkeypatch, requests_per_minute=1)
    # Use up the one allowed write.
    now = int(time.time())
    await cli.post("/listings/3/messages", json=message_body(3, now, "hello"))

    for _ in range(5):
        read_now = int(time.time())
        message = build_read_signable_message(3, read_now)
        resp = await cli.get(
            "/listings/3/messages",
            params={"timestamp": str(read_now), "signature": sign_text(message, SENDER.key)},
        )
        assert resp.status == 200
