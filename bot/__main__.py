#!/usr/bin/env python

import asyncio
import logging
import datetime
import signal

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

from bot.config import load_config
from bot.constants import (
    START_ROUTES, CB_FILE_LIST, CB_EXIT, CB_DOWNLOAD_ALL, CB_SELECT_FILE,
    CB_NEXT_PAGE, CB_PREV_PAGE, CB_DOWNLOAD_TODAY, CB_DOWNLOAD_LAST_SUNDAY,
    CB_SIX_NEXT_PAGE, CB_SIX_PREV_PAGE, CB_FILE_PREFIX,
)
from bot.context import CustomContext, ChatData
from bot.handlers.start import start
from bot.handlers.file_list import one, next_page, prev_page
from bot.handlers.download import (
    three, six, seven, six_next_page, six_prev_page,
    download_today, download_last_sunday,
)
from bot.handlers.common import end
from bot.server.tokens import TokenStore
from bot.server.app import create_app, run_server, cleanup_tokens_periodically
from bot.utils import periodic_clean_archives

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def main():
    cfg = load_config()

    # Setup token store and aiohttp server if configured
    token_store = None
    http_runner = None
    if cfg.file_server_public_url:
        token_store = TokenStore(ttl=cfg.file_server_token_ttl)
        app = create_app(token_store, cfg.mount_path)
        http_runner = await run_server(app, port=cfg.file_server_port)
        asyncio.create_task(cleanup_tokens_periodically(token_store))
        logger.info(
            "HTTP file server enabled: %s", cfg.file_server_public_url
        )
    else:
        logger.info(
            "HTTP file server disabled "
            "(FILE_SERVER_PUBLIC_URL not set, using archive+split fallback)"
        )

    # Background archive cleanup
    asyncio.create_task(
        periodic_clean_archives(
            cfg.mount_path, max_age_seconds=3600, interval=1800
        )
    )

    # Build PTB application
    context_types = ContextTypes(context=CustomContext, chat_data=ChatData)
    application = Application.builder().token(
        cfg.telegram_token
    ).context_types(context_types).build()

    # Store config and shared objects in bot_data
    application.bot_data['config'] = cfg
    application.bot_data['bot_start_time'] = datetime.datetime.now()
    application.bot_data['archive_semaphore'] = asyncio.Semaphore(
        cfg.archive_semaphore_limit
    )
    if token_store:
        application.bot_data['token_store'] = token_store

    # Register conversation handler
    usb_handler = CommandHandler("usb", start)
    conv_handler = ConversationHandler(
        entry_points=[usb_handler],
        states={
            START_ROUTES: [
                CallbackQueryHandler(
                    one, pattern=f"^{CB_FILE_LIST}$"
                ),
                CallbackQueryHandler(
                    three, pattern=f"^{CB_DOWNLOAD_ALL}$"
                ),
                CallbackQueryHandler(
                    six, pattern=f"^{CB_SELECT_FILE}$"
                ),
                CallbackQueryHandler(
                    end, pattern=f"^{CB_EXIT}$"
                ),
                CallbackQueryHandler(
                    next_page, pattern=f"^{CB_NEXT_PAGE}$"
                ),
                CallbackQueryHandler(
                    prev_page, pattern=f"^{CB_PREV_PAGE}$"
                ),
                CallbackQueryHandler(
                    download_today, pattern=f"^{CB_DOWNLOAD_TODAY}$"
                ),
                CallbackQueryHandler(
                    download_last_sunday,
                    pattern=f"^{CB_DOWNLOAD_LAST_SUNDAY}$"
                ),
                CallbackQueryHandler(
                    six_next_page, pattern=f"^{CB_SIX_NEXT_PAGE}$"
                ),
                CallbackQueryHandler(
                    six_prev_page, pattern=f"^{CB_SIX_PREV_PAGE}$"
                ),
                CallbackQueryHandler(
                    seven, pattern=f"^{CB_FILE_PREFIX}.*$"
                ),
            ]
        },
        fallbacks=[usb_handler],
    )
    application.add_handler(conv_handler)

    # Run PTB with manual lifecycle (not blocking run_polling)
    stop_event = asyncio.Event()

    async with application:
        await application.start()
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES
        )
        logger.info("Bot started polling")

        # Wait for stop signal
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        await stop_event.wait()
        logger.info("Shutting down...")

        await application.updater.stop()
        await application.stop()

    # Cleanup HTTP server
    if http_runner:
        await http_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
