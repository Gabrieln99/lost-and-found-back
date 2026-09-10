import time

from eth_account import Account
from eth_account.messages import encode_defunct

# The exact canonical format a client must sign (EIP-191 personal_sign --
# e.g. ethers.js's `signer.signMessage(...)`, or MetaMask's personal_sign)
# to authenticate a chat message. See CLAUDE.md's storage-service section
# for the full documented format and rationale; the frontend must build
# this exact string byte-for-byte.
MESSAGE_PREFIX = "lost-and-found:message:v1"

# How far a message's claimed timestamp may drift from the server's clock
# before it's rejected outright. This bounds (but doesn't fully prevent)
# replay of an intercepted (message, signature) pair to this window -- an
# exact resend within the window is separately blocked by the messages
# table's UNIQUE (listing_id, sender, timestamp) constraint. Full replay
# resistance (e.g. a server-issued nonce) isn't implemented: this service
# holds no funds and only brokers a temporary handover chat, so the same
# "proportionate for this project's scope" reasoning as the rate-limiting/
# no-auth-layer decision applies here too -- see CLAUDE.md.
TIMESTAMP_TOLERANCE_SECONDS = 300


class SignatureError(Exception):
    """Raised when a signature is malformed / can't be recovered at all.
    Never raised just because the recovered address is unexpected -- that
    authorization decision belongs to the caller, not to signature
    verification itself."""


def build_read_signable_message(listing_id: int, timestamp: int) -> str:
    """Signable string for authenticating a *read* of a listing's message
    thread (GET), separate from build_signable_message's send/write
    format so a read-authorization signature can never be replayed as a
    message send (or vice versa) -- the distinct prefix domain-separates
    the two. See CLAUDE.md for why reads require this at all: message
    bodies may contain real coordination details (meeting spot, phone
    number), unlike the already-public on-chain/IPFS listing data."""
    return f"lost-and-found:read-messages:v1:{listing_id}:{timestamp}"


def build_signable_message(listing_id: int, timestamp: int, body: str) -> str:
    """Reconstructs the exact string a client must have signed. The server
    never parses fields out of a signed message -- it independently
    rebuilds this same string from trusted inputs (listing_id from the
    URL, timestamp/body from the validated request body) and checks that
    reconstruction against the signature. That side-steps any ambiguity
    from `body` containing characters that look like the format's own
    delimiters, since nothing is ever split back apart."""
    return f"{MESSAGE_PREFIX}:{listing_id}:{timestamp}:{body}"


def recover_signer(message: str, signature: str) -> str:
    """Recovers and returns the checksummed address that produced
    `signature` over `message` via EIP-191 personal_sign. Raises
    SignatureError if the signature is malformed."""
    try:
        signable = encode_defunct(text=message)
        return Account.recover_message(signable, signature=signature)
    except SignatureError:
        raise
    except Exception as exc:  # eth_account raises several exception types
        raise SignatureError(f"Invalid signature: {exc}") from exc


def is_timestamp_fresh(timestamp: int, *, now: float | None = None) -> bool:
    """Whether `timestamp` (Unix epoch seconds) is within
    TIMESTAMP_TOLERANCE_SECONDS of the current time. `now` is injectable
    for tests; production callers should never pass it."""
    reference = now if now is not None else time.time()
    return abs(reference - timestamp) <= TIMESTAMP_TOLERANCE_SECONDS
