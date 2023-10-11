#!/usr/bin/env python

import os
import logging
from time import sleep
from typing import Optional
import telegram
from dotenv import load_dotenv
from core import FilesData, build_table, get_chunks
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


# старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    context.chat_data.start_message = update.message.id
    logger.info("User %s started the conversation.", user.first_name)
    keyboard = [
        [InlineKeyboardButton("Посмотреть файлы", callback_data=str(ONE))],
        [InlineKeyboardButton("Выход", callback_data=str(TWO))],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Привет {user.first_name}\n"
        "Тут инфа по флешке: \n"
        "SN:\n"
        "дата подключения: \n"
        "Занятое место:",
        reply_markup=reply_markup)
    return START_ROUTES


# тут показываем список и варианты скачивания
async def one(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Скачать всё", callback_data=str(THREE))],
        # [InlineKeyboardButton(
        #     "Скачать только за сегодня", callback_data=str(FOUR))],
        # [InlineKeyboardButton(
        #     "Скачать только за последний час", callback_data=str(FITH))],
        [InlineKeyboardButton("Скачать конкретный файл",
                              callback_data=str(SIX))],
        [InlineKeyboardButton("Выход", callback_data=str(TWO))],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    files = FilesData()
    files.get_files(path=MOUNT_PATH)

    audio_files = [
        (f.name, f.h_size) for f in files.file_list
    ]

    files_table = build_table(audio_files, "name", "size")
    futter_table = build_table(
        [("full size :", files.h_size_sum,)], "all files :", files.count
    )
    message = f'```\n{files_table}\n```\n```\n{futter_table}\n```'
    try:
        await query.edit_message_text(
            text=message,
            parse_mode=telegram.constants.ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup
        )
    except Exception as err:
        await query.edit_message_text(
            text=f"упс, что-то пошло не так :\n{err}",
            reply_markup=reply_markup
        )
    return START_ROUTES


# тут кнопки скачать отдельный файл и варианты возврата
async def six(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    files = FilesData()
    files.get_files(path=MOUNT_PATH)
    buttons_list = [
        [InlineKeyboardButton(
            text=" ".join((f.name, f.h_size)),
            callback_data="file_to_download:" + f.file
        )] for f in files.file_list
    ]
    print(context.update)
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Назад", callback_data=str(ONE))],
        [InlineKeyboardButton("Выход", callback_data=str(TWO))]
    ]
    reply_markup = InlineKeyboardMarkup(buttons_list + keyboard)

    try:
        await query.edit_message_text(
            text="Какой файл?",
            reply_markup=reply_markup
        )
    except Exception as err:
        await query.edit_message_text(
            text=f"упс, что-то пошло не так :\n{err}",
            reply_markup=reply_markup
        )
        return START_ROUTES
    return START_ROUTES


# тут скачать отдельный файл и варианты возврат
async def seven(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    files = FilesData()
    files.get_files(path=MOUNT_PATH)
    buttons_list = [
        [InlineKeyboardButton(
            text=" ".join((f.name, f.h_size)),
            callback_data="file_to_download:" + f.file
        )] for f in files.file_list
    ]
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Назад", callback_data=str(SIX))],
        [InlineKeyboardButton("Выход", callback_data=str(TWO))]
    ]
    reply_markup = InlineKeyboardMarkup(buttons_list[:15] + keyboard)
    file = update.callback_query.data.split(":", maxsplit=1)[-1]

    await query.delete_message()
    loading_message = await context.bot.send_message(
        text="загружаю...",
        chat_id=update.effective_chat.id
    )
    try:
        media = [telegram.InputMediaAudio(
            open(file, "rb"))]
        await context.bot.send_media_group(
            chat_id=update.effective_chat.id,
            media=media
        )
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=loading_message.message_id
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Загрузка завершена, что дальше?", reply_markup=reply_markup
        )
    except Exception as err:
        await context.bot.edit_message_text(
            message_id=loading_message.message_id,
            chat_id=loading_message.chat_id,
            text=f"упс, что-то пошло не так :\n{err}",
            reply_markup=reply_markup
        )
        logger.error(err)
        return START_ROUTES
    return START_ROUTES


# тут скачать все и варианты возврата
async def three(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    files = FilesData()
    files.get_files(path=MOUNT_PATH)
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("Еще раз с начала", callback_data=str(ONE))],
        [InlineKeyboardButton("Выход", callback_data=str(TWO))]
    ]
    audio_files_chunks = get_chunks(files.file_list)
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.delete_message()
    loading_message = await context.bot.send_message(
        text="загружаю...",
        chat_id=update.effective_chat.id
    )
    try:
        for chunk in audio_files_chunks:
            media = [telegram.InputMediaAudio(
                open(file, "rb")) for file in chunk]
            await context.bot.send_media_group(
                chat_id=update.effective_chat.id,
                media=media
            )
            sleep(2)
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=loading_message.message_id
        )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Загрузка завершена, что дальше?", reply_markup=reply_markup
        )
    except Exception as err:
        await context.bot.edit_message_text(
            message_id=loading_message.message_id,
            chat_id=loading_message.chat_id,
            text=f"упс, что-то пошло не так :\n{err}",
            reply_markup=reply_markup
        )
        logger.error(err)
        return START_ROUTES
    return START_ROUTES


# конец
async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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


def main() -> None:
    """Run the bot."""
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
                # CallbackQueryHandler(two, pattern="^" + str(TWO) + "$"),
                CallbackQueryHandler(three, pattern="^" + str(THREE) + "$"),
                # CallbackQueryHandler(four, pattern="^" + str(FOUR) + "$"),
                # CallbackQueryHandler(fith, pattern="^" + str(FITH) + "$"),
                CallbackQueryHandler(six, pattern="^" + str(SIX) + "$"),
                CallbackQueryHandler(seven, pattern="^file_to_download:.*"),
                CallbackQueryHandler(end, pattern="^" + str(TWO) + "$"),
            ]
        },
        fallbacks=[usb_handler],
    )

    application.add_handler(conv_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
