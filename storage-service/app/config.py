import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


DEFAULT_CORS_ALLOWED_ORIGIN = "http://localhost:5173"

# A small, deliberately conservative default for a university demo: enough
# headroom for a real user publishing/browsing listings, low enough to make
# casually spamming the endpoint burn through the Pinata quota impractical.
# See CLAUDE.md's storage-service section for the reasoning behind rate
# limiting (yes) vs. an auth/API-key layer (no) at this project's scope.
DEFAULT_RATE_LIMIT_REQUESTS_PER_MINUTE = 10

# Deployed LostAndFound contract address on Sepolia (deployments/sepolia.json
# at the repo root is the source of truth). Used as a fallback default so
# local dev works without extra setup; CONTRACT_ADDRESS must be updated here
# (and in the deployed environment's env vars) if the contract is ever
# redeployed to a new address -- see deployments/sepolia.json's own note.
DEFAULT_CONTRACT_ADDRESS = "0x1945e05F857505C4282168d7Fa2974b36353B8d1"

# Where the messages SQLite database file lives. ":memory:" (used by tests)
# gives an isolated, non-persistent database. On Render's ephemeral
# filesystem, the default relative path does NOT survive a redeploy/restart
# -- see CLAUDE.md's storage-service section; this is documented there as
# an accepted limitation of "temporary" contact storage, not a bug.
DEFAULT_MESSAGES_DB_PATH = "messages.db"


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    pinata_jwt: str
    cors_allowed_origin: str
    rate_limit_requests_per_minute: int
    sepolia_rpc_url: str
    contract_address: str
    messages_db_path: str


def load_config() -> Config:
    return Config(
        pinata_jwt=os.environ.get("PINATA_JWT", ""),
        # `or` (not dict.get's default) so a blank CORS_ALLOWED_ORIGIN= line
        # in .env.example / a real .env still falls back to the default,
        # rather than resolving to an empty-string origin.
        cors_allowed_origin=os.environ.get("CORS_ALLOWED_ORIGIN") or DEFAULT_CORS_ALLOWED_ORIGIN,
        rate_limit_requests_per_minute=_int_env(
            "RATE_LIMIT_REQUESTS_PER_MINUTE", DEFAULT_RATE_LIMIT_REQUESTS_PER_MINUTE
        ),
        sepolia_rpc_url=os.environ.get("SEPOLIA_RPC_URL", ""),
        contract_address=os.environ.get("CONTRACT_ADDRESS") or DEFAULT_CONTRACT_ADDRESS,
        messages_db_path=os.environ.get("MESSAGES_DB_PATH") or DEFAULT_MESSAGES_DB_PATH,
    )
