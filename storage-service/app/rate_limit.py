import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from aiohttp import web

from .responses import error_response

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

# Only the two upload endpoints burn Pinata quota; there's nothing else to
# protect (and OPTIONS preflight never reaches this middleware -- see
# cors_middleware, which answers it directly).
RATE_LIMITED_PATHS = {"/upload", "/listing-metadata"}

WINDOW_SECONDS = 60.0


def _client_id(request: web.Request) -> str:
    """Best-effort per-client identifier for rate limiting. Prefers the
    first hop in X-Forwarded-For, since behind a reverse proxy (e.g.
    Render's, in production) request.remote would otherwise resolve to the
    proxy's own address for every client, defeating per-IP limiting.
    Falls back to request.remote for local/direct connections."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote or "unknown"


def rate_limit_middleware(requests_per_minute: int):
    """Simple in-memory, per-process, per-client sliding-window rate
    limiter for the upload endpoints. Deliberately not distributed or
    persistent -- see CLAUDE.md's storage-service section for why that's
    an acceptable tradeoff at this project's scope. A non-positive limit
    disables rate limiting entirely (handy for local dev)."""
    history: dict[str, deque[float]] = defaultdict(deque)

    @web.middleware
    async def middleware(request: web.Request, handler: Handler) -> web.StreamResponse:
        if requests_per_minute <= 0 or request.path not in RATE_LIMITED_PATHS:
            return await handler(request)

        client_id = _client_id(request)
        timestamps = history[client_id]
        now = time.monotonic()

        while timestamps and now - timestamps[0] > WINDOW_SECONDS:
            timestamps.popleft()

        if len(timestamps) >= requests_per_minute:
            return error_response(
                f"Rate limit exceeded: max {requests_per_minute} requests per minute. "
                "Please try again later.",
                status=429,
            )

        timestamps.append(now)
        return await handler(request)

    return middleware
