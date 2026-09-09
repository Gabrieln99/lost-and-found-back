import time

from eth_account import Account
from eth_account.messages import encode_defunct

from app import create_app
from app.contract_reader import ContractReadError, ListingNotFoundError
from app.signing import build_read_signable_message, build_signable_message

OWNER = Account.create()
FINDER = Account.create()
STRANGER = Account.create()


def sign_text(text: str, private_key) -> str:
    signed = Account.sign_message(encode_defunct(text=text), private_key=private_key)
    sig_hex = signed.signature.hex()
    return sig_hex if sig_hex.startswith("0x") else f"0x{sig_hex}"


async def make_client(aiohttp_client, monkeypatch, *, sepolia_rpc_url="http://rpc.example"):
    # MESSAGES_DB_PATH defaults to ":memory:" via conftest.py's autouse fixture.
    if sepolia_rpc_url is None:
        monkeypatch.delenv("SEPOLIA_RPC_URL", raising=False)
    else:
        monkeypatch.setenv("SEPOLIA_RPC_URL", sepolia_rpc_url)
    monkeypatch.delenv("RATE_LIMIT_REQUESTS_PER_MINUTE", raising=False)
    app = create_app()
    return await aiohttp_client(app)


def set_listing_parties(cli, owner=OWNER.address, finder=FINDER.address):
    async def fake_get_listing_parties(_listing_id):
        return owner, finder

    cli.app["contract_reader"].get_listing_parties = fake_get_listing_parties


def set_listing_not_found(cli):
    async def fake_get_listing_parties(listing_id):
        raise ListingNotFoundError(f"Listing {listing_id} does not exist")

    cli.app["contract_reader"].get_listing_parties = fake_get_listing_parties


def set_contract_read_failure(cli):
    async def fake_get_listing_parties(_listing_id):
        raise ContractReadError("RPC unavailable")

    cli.app["contract_reader"].get_listing_parties = fake_get_listing_parties


def post_body(listing_id, timestamp, body, private_key):
    message = build_signable_message(listing_id, timestamp, body)
    return {"timestamp": timestamp, "body": body, "signature": sign_text(message, private_key)}


def read_query(listing_id, timestamp, private_key):
    message = build_read_signable_message(listing_id, timestamp)
    return {"timestamp": str(timestamp), "signature": sign_text(message, private_key)}


def post_message(cli, listing_id, timestamp, body, private_key):
    payload = post_body(listing_id, timestamp, body, private_key)
    return cli.post(f"/listings/{listing_id}/messages", json=payload)


def get_messages(cli, listing_id, timestamp, private_key):
    params = read_query(listing_id, timestamp, private_key)
    return cli.get(f"/listings/{listing_id}/messages", params=params)


class TestPostMessage:
    async def test_owner_can_send_a_message(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)
        now = int(time.time())

        resp = await post_message(cli, 3, now, "Meet at the fountain at noon", OWNER.key)

        assert resp.status == 201
        body = await resp.json()
        assert body["listingId"] == 3
        assert body["sender"].lower() == OWNER.address.lower()
        assert body["body"] == "Meet at the fountain at noon"
        assert body["timestamp"] == now
        assert isinstance(body["id"], int)

    async def test_finder_can_also_send_a_message(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)
        now = int(time.time())

        resp = await post_message(cli, 3, now, "On my way", FINDER.key)

        assert resp.status == 201
        body = await resp.json()
        assert body["sender"].lower() == FINDER.address.lower()

    async def test_a_stranger_cannot_send_a_message(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)
        now = int(time.time())

        resp = await post_message(cli, 3, now, "let me in", STRANGER.key)

        assert resp.status == 403

    async def test_tampering_with_the_body_after_signing_is_rejected(
        self, aiohttp_client, monkeypatch
    ):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)
        now = int(time.time())

        # Sign one body, submit a different one -- the signature no longer
        # recovers to the owner/finder, so this is rejected as
        # unauthorized (not as a malformed-signature error).
        signed_body = post_body(3, now, "original body", OWNER.key)
        signed_body["body"] = "tampered body"

        resp = await cli.post("/listings/3/messages", json=signed_body)

        assert resp.status == 403

    async def test_malformed_signature_is_rejected(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)
        now = int(time.time())

        resp = await cli.post(
            "/listings/3/messages",
            json={"timestamp": now, "body": "hello", "signature": "not-a-signature"},
        )

        assert resp.status == 400
        body = await resp.json()
        assert "error" in body

    async def test_stale_timestamp_is_rejected(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)
        stale = int(time.time()) - 10_000

        resp = await post_message(cli, 3, stale, "hello", OWNER.key)

        assert resp.status == 400

    async def test_blank_body_is_rejected(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)
        now = int(time.time())

        resp = await post_message(cli, 3, now, "   ", OWNER.key)

        assert resp.status == 400

    async def test_oversized_body_is_rejected(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)
        now = int(time.time())

        resp = await post_message(cli, 3, now, "x" * 2001, OWNER.key)

        assert resp.status == 400

    async def test_exact_replay_of_a_previously_accepted_message_is_rejected(
        self, aiohttp_client, monkeypatch
    ):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)
        now = int(time.time())
        payload = post_body(3, now, "hello", OWNER.key)

        first = await cli.post("/listings/3/messages", json=payload)
        second = await cli.post("/listings/3/messages", json=payload)

        assert first.status == 201
        assert second.status == 409

    async def test_nonexistent_listing_returns_404(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_not_found(cli)
        now = int(time.time())

        resp = await post_message(cli, 999, now, "hello", OWNER.key)

        assert resp.status == 404

    async def test_contract_read_failure_returns_502(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_contract_read_failure(cli)
        now = int(time.time())

        resp = await post_message(cli, 3, now, "hello", OWNER.key)

        assert resp.status == 502

    async def test_missing_rpc_url_returns_500(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch, sepolia_rpc_url=None)
        now = int(time.time())

        resp = await post_message(cli, 3, now, "hello", OWNER.key)

        assert resp.status == 500

    async def test_non_integer_listing_id_in_url_returns_400(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        now = int(time.time())

        resp = await cli.post(
            "/listings/not-a-number/messages", json=post_body(3, now, "hello", OWNER.key)
        )

        assert resp.status == 400

    async def test_response_carries_the_cors_header(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)
        now = int(time.time())

        resp = await post_message(cli, 3, now, "hello", OWNER.key)

        assert resp.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"


class TestGetMessages:
    async def test_owner_can_read_an_empty_thread(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)
        now = int(time.time())

        resp = await get_messages(cli, 3, now, OWNER.key)

        assert resp.status == 200
        body = await resp.json()
        assert body == {"messages": []}

    async def test_finder_can_read_the_thread_in_chronological_order(
        self, aiohttp_client, monkeypatch
    ):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)
        base = int(time.time()) - 100

        await post_message(cli, 3, base, "first", OWNER.key)
        await post_message(cli, 3, base + 1, "second", FINDER.key)

        resp = await get_messages(cli, 3, int(time.time()), FINDER.key)

        assert resp.status == 200
        body = await resp.json()
        assert [m["body"] for m in body["messages"]] == ["first", "second"]
        assert body["messages"][0]["sender"].lower() == OWNER.address.lower()
        assert body["messages"][1]["sender"].lower() == FINDER.address.lower()

    async def test_a_stranger_cannot_read_the_thread(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)

        resp = await get_messages(cli, 3, int(time.time()), STRANGER.key)

        assert resp.status == 403

    async def test_missing_signature_query_param_is_rejected(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)

        resp = await cli.get("/listings/3/messages", params={"timestamp": str(int(time.time()))})

        assert resp.status == 400

    async def test_stale_read_timestamp_is_rejected(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)
        stale = int(time.time()) - 10_000

        resp = await get_messages(cli, 3, stale, OWNER.key)

        assert resp.status == 400

    async def test_a_write_signature_cannot_be_reused_to_read(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_parties(cli)
        now = int(time.time())

        # Sign the *write* format, then try to use it as read authorization.
        write_message = build_signable_message(3, now, "")
        signature = sign_text(write_message, OWNER.key)

        resp = await cli.get(
            "/listings/3/messages",
            params={"timestamp": str(now), "signature": signature},
        )

        assert resp.status == 403

    async def test_nonexistent_listing_returns_404(self, aiohttp_client, monkeypatch):
        cli = await make_client(aiohttp_client, monkeypatch)
        set_listing_not_found(cli)

        resp = await get_messages(cli, 999, int(time.time()), OWNER.key)

        assert resp.status == 404
