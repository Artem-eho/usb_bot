import os
import asyncio
import logging
import datetime
from collections import Counter

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.config import Config
from bot.constants import CB_FILE_LIST, CB_EXIT, START_ROUTES
from bot.core import FilesData
from bot.security import is_user_allowed
from bot.utils import error_handler, schedule_menu_deletion

logger = logging.getLogger(__name__)


def make_greeting(user_first_name, files, mount_path, bot_start_time):
    import psutil
    today = datetime.date.today().strftime('%d.%m.%Y')
    ext_counter = Counter(
        os.path.splitext(f.name)[1].lower() for f in files.file_list
    )
    ext_info = ', '.join(
        '{}: {}'.format(k or '[без расширения]', v)
        for k, v in ext_counter.items()
    )
    disk = psutil.disk_usage(mount_path)
    free_gb = disk.free / (1024 ** 3)
    if files.file_list:
        last_file = max(files.file_list, key=lambda f: f.ctime)
        last_file_info = '{}\n({})'.format(
            last_file.name,
            datetime.datetime.fromtimestamp(
                last_file.ctime
            ).strftime('%d.%m.%Y %H:%M:%S')
        )
    else:
        last_file_info = 'Нет файлов'
    uptime = datetime.datetime.now() - bot_start_time
    uptime_str = str(uptime).split('.')[0]
    return (
        f"👋 Привет, {user_first_name}!\n\n"
        f"📅 Сегодня: {today}\n"
        f"📁 Файлов в папке: {len(files.file_list)} ({ext_info})\n"
        f"💾 Свободно на диске: {free_gb: .2f} ГБ\n"
        f"🕑 Аптайм бота: {uptime_str}\n\n"
        f"🆕 Последний файл: \n{last_file_info}"
    )


@error_handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cfg: Config = context.bot_data['config']
    user = update.message.from_user
    if not is_user_allowed(user.id, cfg.filtered_users):
        await update.message.reply_text("⛔️ Доступ запрещён.")
        return ConversationHandler.END

    context.chat_data.start_message = update.message.id
    logger.info("User %s started the conversation.", user.first_name)

    files = FilesData()
    files.get_files(path=cfg.mount_path)
    bot_start_time = context.bot_data['bot_start_time']
    message = make_greeting(
        user.first_name, files, cfg.mount_path, bot_start_time
    )

    keyboard = [
        [InlineKeyboardButton(
            "👀 Посмотреть файлы", callback_data=CB_FILE_LIST
        )],
        [InlineKeyboardButton("🚪 Выход", callback_data=CB_EXIT)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    sent_message = await update.message.reply_text(
        message, reply_markup=reply_markup
    )
    asyncio.create_task(schedule_menu_deletion(
        context, sent_message.chat_id, sent_message.message_id,
        cfg.menu_lifetime_seconds
    ))
    return START_ROUTES
