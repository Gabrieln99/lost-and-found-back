from collections.abc import AsyncIterator

import aiohttp
from aiohttp import web

from .config import load_config
from .listing_metadata import listing_metadata_handler
from .pinata import PinataClient
from .upload import upload_handler


async def _pinata_session_ctx(app: web.Application) -> AsyncIterator[None]:
    async with aiohttp.ClientSession() as session:
        app["pinata_client"] = PinataClient(jwt=app["config"].pinata_jwt, session=session)
        yield


def create_app() -> web.Application:
    app = web.Application()
    app["config"] = load_config()
    app.cleanup_ctx.append(_pinata_session_ctx)
    app.router.add_post("/upload", upload_handler)
    app.router.add_post("/listing-metadata", listing_metadata_handler)
    return app
