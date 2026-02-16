import os
import re
import logging
import datetime
import asyncio

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler
from hurry.filesize import size as h_size_fmt

from bot.config import Config
from bot.constants import (
    START_ROUTES, CB_FILE_LIST, CB_EXIT, CB_FILE_PREFIX,
    CB_SIX_NEXT_PAGE, CB_SIX_PREV_PAGE,
    AUDIO_EXTENSIONS,
)
from bot.core import FilesData
from bot.security import is_user_allowed, is_safe_path, is_file_accessible
from bot.utils import error_handler, log_download, edit_or_send

logger = logging.getLogger(__name__)


async def send_file_to_user(context, chat_id, user, file_obj, cfg: Config):
    """Unified file sending logic.

    - Small files (<=MAX_FILE_SIZE): send directly via Telegram.
    - If Telegram send fails or file is too large: generate HTTP download link.
    - If HTTP server is not configured: report error.
    """
    file_path = file_obj.file
    file_size = file_obj.size if hasattr(file_obj, 'size') else os.path.getsize(file_path)

    if file_size <= cfg.max_file_size:
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in AUDIO_EXTENSIONS:
                with open(file_path, "rb") as f:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=f,
                        filename=os.path.basename(file_path)
                    )
            else:
                with open(file_path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        filename=os.path.basename(file_path)
                    )
            log_download(user, file_path)
            return
        except Exception as exc:
            logger.warning(
                "Telegram send failed for %s: %s", file_path, exc
            )

    # Large file or Telegram send failed — generate HTTP download link
    token_store = context.bot_data.get('token_store')
    public_url = cfg.file_server_public_url

    if not token_store or not public_url:
        filename = os.path.basename(file_path)
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"Не удалось отправить файл {filename}.\n"
                f"HTTP-сервер для скачивания не настроен."
            ),
        )
        return

    token = token_store.create(file_path, user.id)
    base_url = public_url.rstrip('/')
    download_url = f"{base_url}/download/{token}"
    filename = os.path.basename(file_path)
    file_size_h = h_size_fmt(file_size)
    ttl_minutes = cfg.file_server_token_ttl // 60

    if file_size <= cfg.max_file_size:
        text = (
            f"Не удалось выгрузить файл, скачайте его самостоятельно:\n"
            f"<a href=\"{download_url}\">{filename} ({file_size_h})</a>\n"
            f"Ссылка действительна {ttl_minutes} мин."
        )
    else:
        text = (
            f"Файл слишком большой для Telegram.\n"
            f"Скачайте по ссылке: "
            f"<a href=\"{download_url}\">{filename} ({file_size_h})</a>\n"
            f"Ссылка действительна {ttl_minutes} мин."
        )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=telegram.constants.ParseMode.HTML,
        disable_web_page_preview=True,
    )
    log_download(user, file_path)


async def send_files_group(update, context, file_objs, label):
    """Send a group of files (up to all files). Uses ARCHIVE_SEMAPHORE."""
    cfg: Config = context.bot_data['config']
    semaphore: asyncio.Semaphore = context.bot_data['archive_semaphore']

    async with semaphore:
        query = update.callback_query

        if not file_objs:
            await query.answer(
                f"Нет файлов {label}.", show_alert=False
            )
            from bot.handlers.file_list import one
            return await one(update, context)

        await query.answer()

        loading_message = await context.bot.send_message(
            text=f"Загружаю файлы {label}...",
            chat_id=update.effective_chat.id
        )
        try:
            for f in file_objs:
                try:
                    await send_file_to_user(
                        context, update.effective_chat.id,
                        update.effective_user, f, cfg
                    )
                except Exception as err:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=(
                            f"Ошибка при отправке файла "
                            f"{os.path.basename(f.file)}: {err}"
                        )
                    )

            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=loading_message.message_id
            )

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Загрузка завершена!"
            )
        except Exception as err:
            try:
                await context.bot.edit_message_text(
                    message_id=loading_message.message_id,
                    chat_id=loading_message.chat_id,
                    text=f"упс, что-то пошло не так: \n{err}"
                )
            except telegram.error.BadRequest as berr:
                if "Message is not modified" not in str(berr):
                    raise
            logger.error(err)
            return START_ROUTES
        return START_ROUTES


@error_handler
async def three(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Download all files."""
    cfg: Config = context.bot_data['config']
    user = update.effective_user
    if not is_user_allowed(user.id, cfg.filtered_users):
        await update.callback_query.answer(
            "Доступ запрещён.", show_alert=False
        )
        return ConversationHandler.END
    files = FilesData()
    files.get_files(path=cfg.mount_path)
    return await send_files_group(update, context, files.file_list, "все файлы")


@error_handler
async def download_today(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Download files matching today's date pattern in filename."""
    cfg: Config = context.bot_data['config']
    user = update.effective_user
    if not is_user_allowed(user.id, cfg.filtered_users):
        await update.callback_query.answer(
            "Доступ запрещён.", show_alert=False
        )
        return ConversationHandler.END
    files = FilesData()
    files.get_files(path=cfg.mount_path)
    today_str = datetime.date.today().strftime('%Y%m%d')
    today_files = [
        f for f in files.file_list
        if re.search(rf'{today_str}', f.name)
    ]
    return await send_files_group(update, context, today_files, "за сегодня")


@error_handler
async def download_last_sunday(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Download files matching last Sunday's date pattern."""
    cfg: Config = context.bot_data['config']
    user = update.effective_user
    if not is_user_allowed(user.id, cfg.filtered_users):
        await update.callback_query.answer(
            "Доступ запрещён.", show_alert=False
        )
        return ConversationHandler.END
    files = FilesData()
    files.get_files(path=cfg.mount_path)
    today = datetime.date.today()
    if today.weekday() == 6:
        last_sunday = today
    else:
        last_sunday = today - datetime.timedelta(
            days=(today.weekday() + 1) % 7 or 7
        )
    last_sunday_str = last_sunday.strftime('%Y%m%d')
    sunday_files = [
        f for f in files.file_list
        if re.search(rf'{last_sunday_str}', f.name)
    ]
    if not sunday_files:
        await update.callback_query.answer(
            "Нет файлов за последнее воскресенье.", show_alert=False
        )
        from bot.handlers.file_list import one
        return await one(update, context)
    return await send_files_group(
        update, context, sunday_files, "за последнее воскресенье"
    )


@error_handler
async def six(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show file selection list for individual download."""
    cfg: Config = context.bot_data['config']
    user = update.effective_user
    if not is_user_allowed(user.id, cfg.filtered_users):
        await update.callback_query.answer(
            "Доступ запрещён.", show_alert=False
        )
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()

    page = int(context.user_data.get('six_files_page', 0))
    files = FilesData()
    files.get_files(path=cfg.mount_path)
    total_files = len(files.file_list)
    files.file_list.sort(key=lambda f: f.ctime, reverse=True)

    today = datetime.date.today()
    if today.weekday() == 6:
        last_sunday = today
    else:
        last_sunday = today - datetime.timedelta(
            days=(today.weekday() + 1) % 7 or 7
        )
    last_sunday_str = last_sunday.strftime('%Y%m%d')

    start = page * cfg.six_files_page_size
    end = start + cfg.six_files_page_size
    page_files = files.file_list[start:end]

    file_buttons = []
    for f in page_files:
        name = str(f.name)
        file_size = int(f.size)
        h_size = str(f.h_size)
        icons = []
        match = re.search(r'(\d{8})-(\d{6})', name)
        is_church = False
        if match:
            date_str, time_str = match.groups()
            if date_str == last_sunday_str:
                hour = int(time_str[:2])
                if 16 <= hour < 19:
                    is_church = True
        is_archive = file_size > cfg.max_file_size
        if is_church:
            icons.append('💒')
        if is_archive:
            icons.append('📦')
        icon_str = f" {' '.join(icons)}" if icons else ""
        file_buttons.append([
            InlineKeyboardButton(
                f"{name} ({h_size}){icon_str}",
                callback_data=f"{CB_FILE_PREFIX}{name}"
            )
        ])

    pagination_row = []
    if page > 0:
        pagination_row.append(
            InlineKeyboardButton("◀️", callback_data=CB_SIX_PREV_PAGE)
        )
    if end < total_files:
        pagination_row.append(
            InlineKeyboardButton("▶️", callback_data=CB_SIX_NEXT_PAGE)
        )
    if pagination_row:
        file_buttons.append(pagination_row)

    file_buttons += [
        [
            InlineKeyboardButton("🔙 Назад", callback_data=CB_FILE_LIST),
            InlineKeyboardButton("🚪 Выход", callback_data=CB_EXIT),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(file_buttons)

    total_pages = (
        (total_files + cfg.six_files_page_size - 1) // cfg.six_files_page_size
    )
    page_number = page + 1 if total_pages > 0 else 1

    try:
        await edit_or_send(
            query, context,
            text=(
                f"Выберите файл для скачивания:\n"
                f"Страница {page_number} из {total_pages}"
            ),
            reply_markup=reply_markup,
        )
    except telegram.error.BadRequest as err:
        if "Message is not modified" not in str(err):
            raise

    return START_ROUTES


@error_handler
async def six_next_page(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    context.user_data['six_files_page'] = (
        context.user_data.get('six_files_page', 0) + 1
    )
    return await six(update, context)


@error_handler
async def six_prev_page(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    context.user_data['six_files_page'] = max(
        context.user_data.get('six_files_page', 0) - 1, 0
    )
    return await six(update, context)


@error_handler
async def seven(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Download a specific file by name from callback data."""
    cfg: Config = context.bot_data['config']
    user = update.effective_user
    if not is_user_allowed(user.id, cfg.filtered_users):
        await update.callback_query.answer(
            "Доступ запрещён.", show_alert=False
        )
        return ConversationHandler.END

    file_name = update.callback_query.data.split(":", maxsplit=1)[-1].strip()
    files = FilesData()
    files.get_files(path=cfg.mount_path)
    file_obj = next(
        (f for f in files.file_list if f.name == file_name), None
    )

    if (not file_obj
            or not is_safe_path(cfg.mount_path, file_obj.file)
            or not is_file_accessible(file_obj.file)):
        await update.callback_query.answer(
            "Файл не найден или недоступен.", show_alert=False
        )
        return await six(update, context)

    await update.callback_query.answer()
    loading_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="загружаю..."
    )
    try:
        await send_file_to_user(
            context, update.effective_chat.id, user, file_obj, cfg
        )
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=loading_message.message_id
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Загрузка завершена!"
        )
    except Exception as err:
        logger.exception(
            "Ошибка при отправке файла: user_id=%s, file=%s",
            user.id, file_obj.file
        )
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=loading_message.message_id
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"Ошибка при отправке файла "
                f"{os.path.basename(file_obj.file)}: {err}"
            )
        )

    return START_ROUTES
