import asyncio
import logging
from aiohttp import web

from bot.server.tokens import TokenStore
from bot.server.routes import setup_routes

logger = logging.getLogger(__name__)


def create_app(token_store: TokenStore, mount_path: str) -> web.Application:
    app = web.Application()
    app['token_store'] = token_store
    app['mount_path'] = mount_path
    setup_routes(app)
    return app


async def run_server(app: web.Application, host: str = '0.0.0.0', port: int = 8080):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info(f"HTTP file server started on {host}:{port}")
    return runner


async def cleanup_tokens_periodically(token_store: TokenStore, interval: int = 300):
    while True:
        removed = token_store.cleanup_expired()
        if removed:
            logger.info(f"Cleaned up {removed} expired tokens")
        await asyncio.sleep(interval)
