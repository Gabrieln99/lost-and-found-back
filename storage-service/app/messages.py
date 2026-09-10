from aiohttp import web
from pydantic import ValidationError

from . import messages_db
from .contract_reader import ContractReadError, ListingNotFoundError
from .responses import error_response
from .schemas import MessageIn, MessageListResponse, MessageOut
from .signing import (
    SignatureError,
    build_read_signable_message,
    build_signable_message,
    is_timestamp_fresh,
    recover_signer,
)


def _parse_listing_id(request: web.Request) -> int | None:
    raw = request.match_info.get("listing_id", "")
    if not raw.isdigit():
        return None
    return int(raw)


async def _authorize_party(
    request: web.Request, listing_id: int, sender: str
) -> web.Response | None:
    """Returns an error response if `sender` isn't the listing's owner or
    finder (or the listing doesn't exist / can't be read), else None."""
    contract_reader = request.app["contract_reader"]
    try:
        owner, finder = await contract_reader.get_listing_parties(listing_id)
    except ListingNotFoundError:
        return error_response(f"Listing {listing_id} does not exist", status=404)
    except ContractReadError as exc:
        return error_response(str(exc), status=502)

    if sender.lower() not in (owner.lower(), finder.lower()):
        return error_response(
            "Only the listing's owner or finder can access messages for it.", status=403
        )
    return None


async def post_message_handler(request: web.Request) -> web.Response:
    """POST /listings/{listing_id}/messages -- submits a signed chat
    message. See CLAUDE.md's storage-service section for the exact
    signable-message format the client must reproduce."""
    listing_id = _parse_listing_id(request)
    if listing_id is None:
        return error_response("listingId must be a non-negative integer", status=400)

    config = request.app["config"]
    if not config.sepolia_rpc_url:
        return error_response("Server misconfigured: SEPOLIA_RPC_URL is not set", status=500)

    try:
        payload = await request.json()
    except Exception:
        return error_response("Request body must be valid JSON", status=400)

    try:
        message_in = MessageIn(**payload)
    except ValidationError as exc:
        return error_response(str(exc), status=400)

    if not is_timestamp_fresh(message_in.timestamp):
        return error_response(
            "Message timestamp is too far from the server's clock -- please try again.",
            status=400,
        )

    signable = build_signable_message(listing_id, message_in.timestamp, message_in.body)
    try:
        sender = recover_signer(signable, message_in.signature)
    except SignatureError as exc:
        return error_response(str(exc), status=400)

    auth_error = await _authorize_party(request, listing_id, sender)
    if auth_error is not None:
        return auth_error

    conn = request.app["messages_db"]
    try:
        record = await messages_db.insert_message(
            conn,
            listing_id=listing_id,
            sender=sender,
            body=message_in.body,
            timestamp=message_in.timestamp,
        )
    except messages_db.DuplicateMessageError:
        return error_response(
            "A message with this exact timestamp has already been recorded -- "
            "please try again.",
            status=409,
        )

    return web.json_response(MessageOut(**record).model_dump(by_alias=True), status=201)


async def get_messages_handler(request: web.Request) -> web.Response:
    """GET /listings/{listing_id}/messages?timestamp=...&signature=... --
    fetches a listing's message thread. Requires the same wallet-signature
    proof of being the listing's owner/finder as sending a message,
    because a thread's contents may include real coordination details
    (meeting spot, phone number) unlike the already-public listing data;
    the client re-signs (via build_read_signable_message) once per
    thread-open/poll cycle within the timestamp freshness window, reusing
    the exact same verification path as writes rather than a second
    bespoke auth mechanism."""
    listing_id = _parse_listing_id(request)
    if listing_id is None:
        return error_response("listingId must be a non-negative integer", status=400)

    config = request.app["config"]
    if not config.sepolia_rpc_url:
        return error_response("Server misconfigured: SEPOLIA_RPC_URL is not set", status=500)

    timestamp_raw = request.query.get("timestamp", "")
    signature = request.query.get("signature", "")
    if not timestamp_raw.lstrip("-").isdigit() or not signature:
        return error_response(
            "Reading messages requires timestamp and signature query parameters "
            "proving you are the listing's owner or finder.",
            status=400,
        )
    timestamp = int(timestamp_raw)

    if not is_timestamp_fresh(timestamp):
        return error_response(
            "Timestamp is too far from the server's clock -- please try again.", status=400
        )

    signable = build_read_signable_message(listing_id, timestamp)
    try:
        sender = recover_signer(signable, signature)
    except SignatureError as exc:
        return error_response(str(exc), status=400)

    auth_error = await _authorize_party(request, listing_id, sender)
    if auth_error is not None:
        return auth_error

    conn = request.app["messages_db"]
    records = await messages_db.fetch_messages(conn, listing_id)
    response = MessageListResponse(messages=[MessageOut(**r) for r in records])
    return web.json_response(response.model_dump(by_alias=True))
