from collections.abc import AsyncIterator

import aiohttp
from aiohttp import web

from .config import load_config
from .cors import cors_middleware
from .listing_metadata import listing_metadata_handler
from .pinata import PinataClient
from .rate_limit import rate_limit_middleware
from .upload import upload_handler


async def _pinata_session_ctx(app: web.Application) -> AsyncIterator[None]:
    async with aiohttp.ClientSession() as session:
        app["pinata_client"] = PinataClient(jwt=app["config"].pinata_jwt, session=session)
        yield


def create_app() -> web.Application:
    config = load_config()
    app = web.Application(
        # CORS wraps rate limiting so a 429 still carries CORS headers --
        # aiohttp calls middlewares in list order on the way in, so the
        # first entry is outermost on the way out too.
        middlewares=[
            cors_middleware(config.cors_allowed_origin),
            rate_limit_middleware(config.rate_limit_requests_per_minute),
        ]
    )
    app["config"] = config
    app.cleanup_ctx.append(_pinata_session_ctx)
    app.router.add_post("/upload", upload_handler)
    app.router.add_post("/listing-metadata", listing_metadata_handler)
    return app
