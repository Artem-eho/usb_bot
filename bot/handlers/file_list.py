import html
import asyncio
import logging

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import Config
from bot.constants import (
    CB_DOWNLOAD_ALL, CB_DOWNLOAD_TODAY, CB_DOWNLOAD_LAST_SUNDAY,
    CB_SELECT_FILE, CB_EXIT, CB_NEXT_PAGE, CB_PREV_PAGE, START_ROUTES,
)
from bot.core import FilesData, build_table
from bot.security import is_user_allowed
from bot.utils import error_handler, schedule_menu_deletion, edit_or_send
from telegram.ext import ConversationHandler

logger = logging.getLogger(__name__)


@error_handler
async def one(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show file list with pagination and download options."""
    cfg: Config = context.bot_data['config']
    user = update.effective_user
    if not is_user_allowed(user.id, cfg.filtered_users):
        await update.callback_query.answer(
            "Доступ запрещён.", show_alert=False
        )
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()

    page = context.user_data.get('page', 0)
    files = FilesData()
    files.get_files(path=cfg.mount_path)
    total_files = len(files.file_list)
    files.file_list.sort(key=lambda f: f.ctime, reverse=True)

    start = page * cfg.page_size
    end = start + cfg.page_size
    page_files = files.file_list[start:end]

    audio_files = [(f.name, f.h_size) for f in page_files]
    files_table = build_table(audio_files, "name", "size")
    footer_table = build_table(
        [("full size :", files.h_size_sum,)], "all files :", files.count
    )
    files_table_html = html.escape(str(files_table))
    footer_table_html = html.escape(str(footer_table))
    message = f'<pre>{files_table_html}\n{footer_table_html}</pre>'

    keyboard = []
    pagination_row = []
    if page > 0:
        pagination_row.append(
            InlineKeyboardButton("◀️", callback_data=CB_PREV_PAGE)
        )
    if end < total_files:
        pagination_row.append(
            InlineKeyboardButton("▶️", callback_data=CB_NEXT_PAGE)
        )
    if pagination_row:
        keyboard.append(pagination_row)

    keyboard += [
        [InlineKeyboardButton(
            "📥 Скачать всё", callback_data=CB_DOWNLOAD_ALL
        )],
        [InlineKeyboardButton(
            "📅 Скачать за сегодня", callback_data=CB_DOWNLOAD_TODAY
        )],
        [InlineKeyboardButton(
            "💒 Скачать за последнее воскресенье",
            callback_data=CB_DOWNLOAD_LAST_SUNDAY
        )],
        [InlineKeyboardButton(
            "🎼 Скачать конкретный файл", callback_data=CB_SELECT_FILE
        )],
        [InlineKeyboardButton("🚪 Выход", callback_data=CB_EXIT)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        sent = await edit_or_send(
            query, context,
            text=message,
            parse_mode=telegram.constants.ParseMode.HTML,
            reply_markup=reply_markup,
        )
        asyncio.create_task(schedule_menu_deletion(
            context, sent.chat_id, sent.message_id,
            cfg.menu_lifetime_seconds
        ))
    except telegram.error.BadRequest as err:
        if "Message is not modified" not in str(err):
            raise

    return START_ROUTES


@error_handler
async def next_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['page'] = context.user_data.get('page', 0) + 1
    return await one(update, context)


@error_handler
async def prev_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['page'] = max(
        context.user_data.get('page', 0) - 1, 0
    )
    return await one(update, context)
