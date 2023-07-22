#!/usr/bin/env python

import os
import logging
from time import sleep
import telegram
from dotenv import load_dotenv
from core import FilesData
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    filters,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
)

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
MOUNT_PATH = os.getenv('MOUNT_PATH')


# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


files = FilesData()
files.path = MOUNT_PATH


# Stages
START_ROUTES, END_ROUTES = range(2)
# Callback data
ONE, TWO, THREE, FOUR, FITH, SIX = range(6)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send message on `/start`."""
    user = update.message.from_user
    logger.info("User %s started the conversation.", user.first_name)
    keyboard = [
        [
            InlineKeyboardButton("Посмотреть файлы", callback_data=str(ONE)),
            InlineKeyboardButton("Выход", callback_data=str(TWO)),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Тут инфа по флешке: \n"
        "SN:\n"
        "дата подключения: \n"
        "Занятое место:",
        reply_markup=reply_markup)
    return START_ROUTES


async def start_over(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Prompt same text & keyboard as `start` does but not as new message"""
    query = update.callback_query
    await query.answer()
    keyboard = [
        [
            InlineKeyboardButton("Посмотреть файлы", callback_data=str(ONE)),
            InlineKeyboardButton("Выход", callback_data=str(TWO)),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="Сюда пихнуть имя флешки",
        reply_markup=reply_markup
    )
    return START_ROUTES


async def one(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Скачать всё", callback_data=str(THREE))],
        # [InlineKeyboardButton(
        #     "Скачать только за сегодня", callback_data=str(FOUR))],
        # [InlineKeyboardButton(
        #     "Скачать только за последний час", callback_data=str(FITH))],
        # [InlineKeyboardButton("Скачать конкретный файл",
        #                       callback_data=str(SIX))],
        [InlineKeyboardButton("Выход", callback_data=str(TWO))],
    ]
    audio_files = files.get_files_name_list()
    reply_markup = InlineKeyboardMarkup(keyboard)
    file_names = (
        f"Всего файлов: {len(audio_files)}\n"
        "\nСписок файлов:\n"
    )
    for file_name in audio_files:
        file_names = f"{file_names}\n{file_name}"
    await query.edit_message_text(
        text=file_names, reply_markup=reply_markup
    )
    return START_ROUTES


async def three(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Еще раз с начала", callback_data=str(ONE))],
        [InlineKeyboardButton("Выход", callback_data=str(TWO))]
    ]
    audio_files_chunks = files.get_chunks()
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


async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="👋")
    sleep(1)
    await query.delete_message()
    return ConversationHandler.END


def main() -> None:
    """Run the bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    done_handler = MessageHandler(
        # filters.Chat(chat_id=TELEGRAM_CHAT_ID)
        filters.Regex("^Done$"),
        start
    )
    conv_handler = ConversationHandler(
        # entry_points=[CommandHandler("start", start)],
        entry_points=[done_handler],
        states={
            START_ROUTES: [
                CallbackQueryHandler(one, pattern="^" + str(ONE) + "$"),
                # CallbackQueryHandler(two, pattern="^" + str(TWO) + "$"),
                CallbackQueryHandler(three, pattern="^" + str(THREE) + "$"),
                # CallbackQueryHandler(four, pattern="^" + str(FOUR) + "$"),
                # CallbackQueryHandler(fith, pattern="^" + str(FITH) + "$"),
                # CallbackQueryHandler(six, pattern="^" + str(SIX) + "$"),
                CallbackQueryHandler(end, pattern="^" + str(TWO) + "$"),
            ]
        },
        fallbacks=[done_handler],
    )

    application.add_handler(conv_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
