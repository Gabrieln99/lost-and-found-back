from aiohttp import web

from .schemas import ErrorResponse


def error_response(message: str, status: int) -> web.Response:
    return web.json_response(ErrorResponse(error=message).model_dump(), status=status)
