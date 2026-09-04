from aiohttp import web

from app import create_app

if __name__ == "__main__":
    web.run_app(create_app(), port=8080)
