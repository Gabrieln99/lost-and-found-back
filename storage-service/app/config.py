import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


DEFAULT_CORS_ALLOWED_ORIGIN = "http://localhost:5173"


@dataclass(frozen=True)
class Config:
    pinata_jwt: str
    cors_allowed_origin: str


def load_config() -> Config:
    return Config(
        pinata_jwt=os.environ.get("PINATA_JWT", ""),
        # `or` (not dict.get's default) so a blank CORS_ALLOWED_ORIGIN= line
        # in .env.example / a real .env still falls back to the default,
        # rather than resolving to an empty-string origin.
        cors_allowed_origin=os.environ.get("CORS_ALLOWED_ORIGIN") or DEFAULT_CORS_ALLOWED_ORIGIN,
    )
