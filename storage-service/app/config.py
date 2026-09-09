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
    )
