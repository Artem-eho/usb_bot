import os
import glob
import time
import asyncio
import logging
import functools
import traceback
from telegram.ext import ConversationHandler

from bot.constants import START_ROUTES

logger = logging.getLogger(__name__)


def error_handler(func):
    @functools.wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as err:
            user = None
            if hasattr(update, 'effective_user') and update.effective_user:
                user = update.effective_user
            elif hasattr(update, 'message') and update.message:
                user = update.message.from_user
            user_info = (
                f"user_id={getattr(user, 'id', '?')}, "
                f"name={getattr(user, 'first_name', '?')}"
            )
            logger.error(
                f"Ошибка в {func.__name__} | {user_info} | {err}\n"
                f"{traceback.format_exc()}"
            )
            try:
                if hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.answer(
                        "Произошла ошибка. Попробуйте позже.",
                        show_alert=False
                    )
                elif hasattr(update, 'message') and update.message:
                    await update.message.reply_text(
                        "Произошла ошибка. Попробуйте позже.",
                        disable_notification=True
                    )
            except Exception:
                pass
            return ConversationHandler.END
    return wrapper


def log_download(user, file_path):
    logger.info(
        f"User {user.id} ({user.first_name}) скачал файл: {file_path}"
    )


def clean_old_archives(folder, max_age_seconds=3600):
    now = time.time()
    patterns = ["*.zip", "*.zip.part*"]
    for pattern in patterns:
        for file_path in glob.glob(os.path.join(folder, pattern)):
            try:
                if (os.path.isfile(file_path)
                        and now - os.path.getmtime(file_path) > max_age_seconds):
                    os.remove(file_path)
                    logger.info(f"Удалён старый архив: {file_path}")
            except Exception as e:
                logger.warning(
                    f"Ошибка при удалении архива {file_path}: {e}"
                )


async def periodic_clean_archives(folder, max_age_seconds=3600, interval=1800):
    while True:
        clean_old_archives(folder, max_age_seconds)
        await asyncio.sleep(interval)


async def schedule_menu_deletion(context, chat_id, message_id, delay):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(
            chat_id=chat_id, message_id=message_id
        )
    except Exception:
        pass  # Message already deleted or inaccessible
