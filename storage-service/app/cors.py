from collections.abc import Awaitable, Callable

from aiohttp import web

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

ALLOWED_METHODS = "POST, OPTIONS"
ALLOWED_HEADERS = "Content-Type"


def cors_middleware(allowed_origin: str):
    """Adds Access-Control-Allow-Origin (and friends) to every response, and
    answers CORS preflight OPTIONS requests directly -- without this, the
    browser accepts the actual POST (visible as 200 in the network log) but
    blocks the frontend's JS from reading the response cross-origin."""

    @web.middleware
    async def middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
        if request.method == "OPTIONS":
            response: web.StreamResponse = web.Response(status=200)
        else:
            response = await handler(request)

        response.headers["Access-Control-Allow-Origin"] = allowed_origin
        response.headers["Access-Control-Allow-Methods"] = ALLOWED_METHODS
        response.headers["Access-Control-Allow-Headers"] = ALLOWED_HEADERS
        return response

    return middleware
