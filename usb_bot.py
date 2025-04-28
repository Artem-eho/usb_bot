#!/usr/bin/env python

import os
import logging
from time import sleep
from typing import Optional
import telegram
from dotenv import load_dotenv
from core import FilesData, build_table, archive_files, split_file
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    # filters,
    # MessageHandler,
    CommandHandler,
    ContextTypes,
    CallbackContext,
    ConversationHandler,
)
import functools
import traceback
import datetime
import html
import tempfile
import glob
import time
import asyncio
import re

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
MOUNT_PATH = os.getenv('MOUNT_PATH')
FILTERED_USERS = os.getenv('FILTERED_USERS')

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# Stages
START_ROUTES, END_ROUTES = range(2)
# Callback data
ONE, TWO, THREE, FOUR, FITH, SIX = range(6)

MAX_FILE_SIZE = 48 * 1024 * 1024  # 48 МБ
PAGE_SIZE = 10
SIX_FILES_PAGE_SIZE = 8

# Глобальная переменная для аптайма
BOT_START_TIME = datetime.datetime.now()
ARCHIVE_SEMAPHORE = asyncio.Semaphore(20)
MENU_LIFETIME_SECONDS = 15 * 60  # 15 минут


class ChatData:
    """Custom class for start_message."""

    def __init__(self) -> None:
        self.start_message: telegram.Message = None


class CustomContext(CallbackContext):
    """Custom class for context."""

    def __init__(
        self,
        application: Application,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,

    ):
        super().__init__(
            application=application,
            chat_id=chat_id,
            user_id=user_id
        )
        self._message_id: Optional[int] = None

    def save_start_message(self) -> Optional[int]:
        self.chat_data.start_message = self._message_id

    def get_start_message(self) -> Optional[int]:
        return self.chat_data.start_message


def is_user_allowed(user_id: int) -> bool:
    """
    Проверяет, разрешён ли пользователь по user_id.
    FILTERED_USERS может быть списком id через запятую или пустым (разрешить всем).
    """
    filtered = os.environ.get('FILTERED_USERS', '')
    if not filtered:
        return True
    allowed = [u.strip() for u in filtered.split(",") if u.strip()]
    return str(user_id) in allowed


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
            # Сообщение пользователю только через всплывающую подсказку
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


def make_greeting(user_first_name, files, mount_path, bot_start_time):
    import psutil
    import datetime
    from collections import Counter
    today = datetime.date.today().strftime('%d.%m.%Y')
    ext_counter = Counter(os.path.splitext(
        f.name)[1].lower() for f in files.file_list)
    ext_info = ', '.join(
        ('{}: {}'.format(k or '[без расширения]', v) for k, v in ext_counter.items()))
    disk = psutil.disk_usage(mount_path)
    free_gb = disk.free / (1024 ** 3)
    if files.file_list:
        last_file = max(files.file_list, key=lambda f: f.ctime)
        last_file_info = '{}\n({})'.format(
            last_file.name,
            datetime.datetime.fromtimestamp(
                last_file.ctime).strftime('%d.%m.%Y %H:%M:%S')
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


# старт
@error_handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    if not is_user_allowed(user.id):
        await update.message.reply_text(
            "⛔️ Доступ запрещён."
        )
        return ConversationHandler.END
    context.chat_data.start_message = update.message.id
    logger.info("User %s started the conversation.", user.first_name)
    files = FilesData()
    files.get_files(path=MOUNT_PATH)
    message = make_greeting(user.first_name, files, MOUNT_PATH, BOT_START_TIME)
    keyboard = [
        [InlineKeyboardButton("Посмотреть файлы", callback_data=str(ONE))],
        [InlineKeyboardButton("Выход", callback_data=str(TWO))],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    sent_message = await update.message.reply_text(
        message,
        reply_markup=reply_markup)
    # Планируем удаление меню через 15 минут
    asyncio.create_task(schedule_menu_deletion(context, sent_message.chat_id, sent_message.message_id))
    return START_ROUTES


# тут показываем список и варианты скачивания с пагинацией
@error_handler
async def one(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not is_user_allowed(user.id):
        await update.callback_query.answer(
            "⛔️ Доступ запрещён.", show_alert=False
        )
        return ConversationHandler.END
    query = update.callback_query
    await query.answer()
    page = context.user_data.get('page', 0)
    files = FilesData()
    files.get_files(path=MOUNT_PATH)
    total_files = len(files.file_list)
    # Сортируем файлы от самых новых к старым
    files.file_list.sort(key=lambda f: f.ctime, reverse=True)
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_files = files.file_list[start:end]
    audio_files = [
        (f.name, f.h_size) for f in page_files
    ]
    files_table = build_table(audio_files, "name", "size")
    futter_table = build_table(
        [("full size :", files.h_size_sum,)], "all files :", files.count
    )
    files_table_html = html.escape(str(files_table))
    futter_table_html = html.escape(str(futter_table))
    message = f'<pre>{files_table_html}\n{futter_table_html}</pre>'
    keyboard = []
    # Формируем кнопки пагинации в один ряд
    pagination_row = []
    if page > 0:
        pagination_row.append(InlineKeyboardButton("⬅️ Назад", callback_data="prev_page"))
    if end < total_files:
        pagination_row.append(InlineKeyboardButton("Вперёд ➡️", callback_data="next_page"))
    if pagination_row:
        keyboard.append(pagination_row)
    keyboard += [
        [InlineKeyboardButton("Скачать всё", callback_data=str(THREE))],
        [InlineKeyboardButton("Скачать за сегодня", callback_data="download_today")],
        [InlineKeyboardButton("Скачать за последнее воскресенье", callback_data="download_last_sunday")],
        [InlineKeyboardButton("Скачать конкретный файл", callback_data=str(SIX))],
        [
            InlineKeyboardButton("🚪 Выход", callback_data=str(TWO))
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        sent = await query.edit_message_text(
            text=message,
            parse_mode=telegram.constants.ParseMode.HTML,
            reply_markup=reply_markup
        )
        # Планируем удаление меню через 15 минут
        asyncio.create_task(schedule_menu_deletion(context, sent.chat_id, sent.message_id))
    except telegram.error.BadRequest as err:
        if "Message is not modified" in str(err):
            pass
        else:
            raise
    return START_ROUTES


# обработчики пагинации
@error_handler
async def next_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['page'] = context.user_data.get('page', 0) + 1
    return await one(update, context)


@error_handler
async def prev_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['page'] = max(context.user_data.get('page', 0) - 1, 0)
    return await one(update, context)


# обработчик скачивания файлов за сегодня
@error_handler
async def download_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not is_user_allowed(user.id):
        await update.callback_query.answer(
            "⛔️ Доступ запрещён.", show_alert=False
        )
        return ConversationHandler.END
    files = FilesData()
    files.get_files(path=MOUNT_PATH)
    today = datetime.date.today()
    today_str = today.strftime('%Y%m%d')
    today_files = [
        f for f in files.file_list
        if re.search(rf'{today_str}', f.name)
    ]
    return await send_files_group(update, context, today_files, "за сегодня")


# обработчик скачивания файлов за последнее воскресенье
@error_handler
async def download_last_sunday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not is_user_allowed(user.id):
        await update.callback_query.answer(
            "⛔️ Доступ запрещён.", show_alert=False
        )
        return START_ROUTES
    files = FilesData()
    files.get_files(path=MOUNT_PATH)
    today = datetime.date.today()
    if today.weekday() == 6:
        last_sunday = today
    else:
        last_sunday = today - datetime.timedelta(days=(today.weekday() + 1) % 7 or 7)
    last_sunday_str = last_sunday.strftime('%Y%m%d')
    sunday_files = [
        f for f in files.file_list
        if re.search(rf'{last_sunday_str}', f.name)
    ]
    if not sunday_files:
        await update.callback_query.answer(
            "Нет файлов за последнее воскресенье.", show_alert=False
        )
        return await one(update, context)
    return await send_files_group(update, context, sunday_files, "за последнее воскресенье")


# универсальная функция отправки группы файлов (до 10 за раз)
async def send_files_group(update, context, file_objs, label):
    async with ARCHIVE_SEMAPHORE:
        query = update.callback_query
        await query.answer()
        if not file_objs:
            await update.callback_query.answer(
                f"Нет файлов {label}.", show_alert=False
            )
            # Оставляем меню открытым
            return await one(update, context)
        loading_message = await context.bot.send_message(
            text=f"Загружаю файлы {label}...",
            chat_id=update.effective_chat.id
        )
        try:
            for f in file_objs:
                try:
                    file_size = os.path.getsize(f.file)
                    if file_size <= MAX_FILE_SIZE:
                        # Отправляем как аудио (если mp3/wav) или как документ
                        ext = os.path.splitext(f.file)[1].lower()
                        if ext in ['.mp3', '.wav', '.ogg', '.m4a']:
                            await context.bot.send_audio(
                                chat_id=update.effective_chat.id,
                                audio=open(f.file, "rb"),
                                filename=os.path.basename(f.file)
                            )
                        else:
                            await context.bot.send_document(
                                chat_id=update.effective_chat.id,
                                document=open(f.file, "rb"),
                                filename=os.path.basename(f.file)
                            )
                        log_download(update.effective_user, f.file)
                    else:
                        # Архивируем и отправляем архив/части
                        with tempfile.TemporaryDirectory() as tmpdir:
                            archive_path = os.path.join(tmpdir, f"{os.path.basename(f.file)}.zip")
                            archive_files([f.file], archive_path)
                            archive_size = os.path.getsize(archive_path)
                            if archive_size <= MAX_FILE_SIZE:
                                send_files = [archive_path]
                            else:
                                send_files = split_file(archive_path, MAX_FILE_SIZE)
                            for part in send_files:
                                await context.bot.send_document(
                                    chat_id=update.effective_chat.id,
                                    document=open(part, "rb"),
                                    filename=os.path.basename(part)
                                )
                                log_download(update.effective_user, part)
                except Exception as err:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"Ошибка при отправке файла {os.path.basename(f.file)}: {err}"
                    )
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=loading_message.message_id
            )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    "<b>Загрузка завершена!</b>\n"
                    "<i>Если архив был разбит на части, скачайте все части в одну папку.</i>\n\n"
                    "<b>\U0001F4C1 Инструкция по склейке и распаковке:</b>\n"
                    "\n"
                    "<b>\U0001F427 Linux/macOS:</b>\n"
                    "<code>cat archive.zip.part* &gt; archive.zip\nunzip archive.zip</code>\n\n"
                    "<b>\U0001F5A5 Windows (PowerShell):</b>\n"
                    "<code>Get-Content archive.zip.part* -Encoding Byte -ReadCount 0 | Set-Content archive.zip -Encoding Byte\nExpand-Archive archive.zip</code>\n\n"
                    "<b>\U0001F40D Windows (cmd):</b>\n"
                    "<code>copy /b archive.zip.part* archive.zip</code>\n\n"
                    "<b>\U0001F40D Универсально (Python):</b>\n"
                    "<code>python -c \"with open('archive.zip','wb') as w: i=0\nwhile True:\n f='archive.zip.part'+str(i)\n if not __import__('os').path.exists(f): break\n w.write(open(f,'rb').read()); i+=1\"\nunzip archive.zip</code>\n"
                    ""
                ),
                parse_mode=telegram.constants.ParseMode.HTML
            )
        except Exception as err:
            try:
                await context.bot.edit_message_text(
                    message_id=loading_message.message_id,
                    chat_id=loading_message.chat_id,
                    text=f"упс, что-то пошло не так: \n{err}"
                )
            except telegram.error.BadRequest as berr:
                if "Message is not modified" in str(berr):
                    pass
                else:
                    raise
            logger.error(err)
            return START_ROUTES
        return START_ROUTES


# тут скачать все и варианты возврата
@error_handler
async def three(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not is_user_allowed(user.id):
        await update.callback_query.answer(
            "⛔️ Доступ запрещён.", show_alert=False
        )
        return ConversationHandler.END
    files = FilesData()
    files.get_files(path=MOUNT_PATH)
    return await send_files_group(update, context, files.file_list, "все файлы")


# конец
@error_handler
async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not is_user_allowed(user.id):
        await update.callback_query.answer(
            "⛔️ Доступ запрещён.", show_alert=False
        )
        return ConversationHandler.END
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="👋")
    sleep(1)
    await query.delete_message()
    await context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=context.get_start_message()
    )
    return ConversationHandler.END


@error_handler
async def six(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not is_user_allowed(user.id):
        await update.callback_query.answer(
            "⛔️ Доступ запрещён.", show_alert=False
        )
        return START_ROUTES
    query = update.callback_query
    await query.answer()
    # Получаем текущую страницу для выбора файла
    page = int(context.user_data.get('six_files_page', 0))
    files = FilesData()
    if not getattr(files, 'file_list', None) and MOUNT_PATH:
        files.get_files(path=MOUNT_PATH)
    total_files = len(files.file_list)
    # Сортируем файлы от самых новых к старым
    files.file_list.sort(key=lambda f: f.ctime, reverse=True)
    last_sunday = None
    today = datetime.date.today()
    if today.weekday() == 6:
        last_sunday = today
    else:
        last_sunday = today - datetime.timedelta(days=(today.weekday() + 1) % 7 or 7)
    last_sunday_str = last_sunday.strftime('%Y%m%d')
    start = page * SIX_FILES_PAGE_SIZE
    end = start + SIX_FILES_PAGE_SIZE
    page_files = files.file_list[start:end]
    # Формируем кнопки файлов с иконкой архиватора для больших файлов и 💒 для воскресных 16:00-19:00
    file_buttons = []
    for f in page_files:
        name = str(f.name)
        size = int(f.size)
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
        is_archive = size > MAX_FILE_SIZE
        if is_church:
            icons.append('💒')
        if is_archive:
            icons.append('📦')
        icon_str = f" {' '.join(icons)}" if icons else ""
        print('DEBUG button:', f"{name} ({h_size}){icon_str}")
        file_buttons.append([
            InlineKeyboardButton(
                f"{name} ({h_size}){icon_str}",
                callback_data=f"file_to_download:{name}"
            )
        ])
    # Кнопки пагинации файлов в один ряд
    pagination_row = []
    if page > 0:
        pagination_row.append(InlineKeyboardButton("⬅️ Назад", callback_data="six_prev_page"))
    if end < total_files:
        pagination_row.append(InlineKeyboardButton("Вперёд ➡️", callback_data="six_next_page"))
    if pagination_row:
        file_buttons.append(pagination_row)
    # Кнопки возврата
    file_buttons += [
        [
            InlineKeyboardButton("⬅️ Назад", callback_data=str(ONE)),
            InlineKeyboardButton("🚪 Выход", callback_data=str(TWO))
        ]
    ]
    reply_markup = InlineKeyboardMarkup(file_buttons)
    # Вычисляем номер страницы и всего страниц
    total_pages = (total_files + SIX_FILES_PAGE_SIZE - 1) // SIX_FILES_PAGE_SIZE
    page_number = page + 1 if total_pages > 0 else 1
    try:
        await query.edit_message_text(
            text=f"Выберите файл для скачивания:\nСтраница {page_number} из {total_pages}",
            reply_markup=reply_markup
        )
    except telegram.error.BadRequest as err:
        if "Message is not modified" in str(err):
            pass
        else:
            raise
    return START_ROUTES


@error_handler
async def six_next_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['six_files_page'] = context.user_data.get('six_files_page', 0) + 1
    return await six(update, context)


@error_handler
async def six_prev_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['six_files_page'] = max(context.user_data.get('six_files_page', 0) - 1, 0)
    return await six(update, context)


@error_handler
async def seven(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not is_user_allowed(user.id):
        await update.callback_query.answer(
            "⛔️ Доступ запрещён.", show_alert=False
        )
        return START_ROUTES
    file = update.callback_query.data.split(":", maxsplit=1)[-1].strip()
    # Проверка безопасности пути и существования файла
    if not is_safe_path(MOUNT_PATH, file) or not is_file_accessible(file):
        await update.callback_query.answer(
            "Файл не найден или недоступен.", show_alert=False
        )
        # Оставляем меню открытым
        return await six(update, context)
    await update.callback_query.answer()
    loading_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="загружаю..."
    )
    try:
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=open(file, "rb"),
            filename=os.path.basename(file)
        )
        log_download(user, file)
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=loading_message.message_id
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Загрузка завершена!"
        )
    except Exception as err:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=loading_message.message_id
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Ошибка при отправке файла {os.path.basename(file)}: {err}"
        )
    return START_ROUTES


def check_env_vars():
    required = ["TELEGRAM_TOKEN", "MOUNT_PATH"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        raise RuntimeError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}")


def is_safe_path(base_path, path):
    base_path = os.path.realpath(base_path)
    path = os.path.realpath(path)
    return os.path.commonpath([base_path]) == os.path.commonpath([base_path, path])


def is_file_accessible(path):
    return os.path.isfile(path) and os.access(path, os.R_OK)


def log_download(user, file_path):
    logger.info(f"User {user.id} ({user.first_name}) скачал файл: {file_path}")


def clean_old_archives(folder, max_age_seconds=3600):
    now = time.time()
    patterns = ["*.zip", "*.zip.part*"]
    for pattern in patterns:
        for file_path in glob.glob(os.path.join(folder, pattern)):
            try:
                if os.path.isfile(file_path) and now - os.path.getmtime(file_path) > max_age_seconds:
                    os.remove(file_path)
                    logger.info(f"Удалён старый архив: {file_path}")
            except Exception as e:
                logger.warning(f"Ошибка при удалении архива {file_path}: {e}")


async def periodic_clean_archives(folder, max_age_seconds=3600, interval=1800):
    while True:
        clean_old_archives(folder, max_age_seconds)
        await asyncio.sleep(interval)


def send_file_with_logging(context, chat_id, user, file_path):
    try:
        with open(file_path, "rb") as f:
            context.bot.send_document(
                chat_id=chat_id,
                document=f,
                filename=os.path.basename(file_path)
            )
        log_download(user, file_path)
    except Exception as err:
        context.bot.send_message(
            chat_id=chat_id,
            text=f"Ошибка при отправке файла {os.path.basename(file_path)}: {err}"
        )


async def schedule_menu_deletion(context, chat_id, message_id, delay=MENU_LIFETIME_SECONDS):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        pass  # Сообщение уже удалено или недоступно


def main() -> None:
    check_env_vars()
    # Запуск фоновой задачи очистки архивов
    loop = asyncio.get_event_loop()
    loop.create_task(periodic_clean_archives(MOUNT_PATH, max_age_seconds=3600, interval=1800))
    context_types = ContextTypes(context=CustomContext, chat_data=ChatData)
    application = Application.builder().token(
        TELEGRAM_TOKEN
    ).context_types(context_types).build()
    # done_handler = MessageHandler(
    #     filters.Regex("^Done$"),
    #     start
    # )
    usb_handler = CommandHandler("usb", start)
    conv_handler = ConversationHandler(
        entry_points=[usb_handler],
        states={
            START_ROUTES: [
                CallbackQueryHandler(one, pattern="^" + str(ONE) + "$"),
                CallbackQueryHandler(three, pattern="^" + str(THREE) + "$"),
                CallbackQueryHandler(six, pattern="^" + str(SIX) + "$"),
                CallbackQueryHandler(end, pattern="^" + str(TWO) + "$"),
                CallbackQueryHandler(next_page, pattern="^next_page$"),
                CallbackQueryHandler(prev_page, pattern="^prev_page$"),
                CallbackQueryHandler(download_today, pattern="^download_today$"),
                CallbackQueryHandler(download_last_sunday, pattern="^download_last_sunday$"),
                CallbackQueryHandler(six_next_page, pattern="^six_next_page$"),
                CallbackQueryHandler(six_prev_page, pattern="^six_prev_page$"),
                CallbackQueryHandler(seven, pattern="^file_to_download:.*$"),
            ]
        },
        fallbacks=[usb_handler],
    )

    application.add_handler(conv_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
