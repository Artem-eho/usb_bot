import os
import logging
from urllib.parse import quote
from aiohttp import web

from bot.security import is_safe_path

logger = logging.getLogger(__name__)


def setup_routes(app: web.Application):
    app.router.add_get('/download/{token}', download_handler)
    app.router.add_get('/health', health_handler)


async def download_handler(request: web.Request) -> web.Response:
    token_store = request.app['token_store']
    mount_path = request.app['mount_path']
    token = request.match_info['token']

    info = token_store.consume(token)
    if info is None:
        raise web.HTTPNotFound(text="Link expired or invalid.")

    file_path = info.file_path

    if not is_safe_path(mount_path, file_path):
        logger.warning(
            f"Path traversal attempt: token={token}, path={file_path}"
        )
        raise web.HTTPForbidden(text="Access denied.")

    if not os.path.isfile(file_path):
        raise web.HTTPNotFound(text="File not found.")

    filename = os.path.basename(file_path)
    response = web.FileResponse(file_path)
    encoded_filename = quote(filename)
    response.headers['Content-Disposition'] = (
        f"attachment; filename=\"{encoded_filename}\"; "
        f"filename*=UTF-8''{encoded_filename}"
    )
    return response


async def health_handler(request: web.Request) -> web.Response:
    token_store = request.app['token_store']
    return web.json_response({
        'status': 'ok',
        'active_tokens': token_store.active_count,
    })
