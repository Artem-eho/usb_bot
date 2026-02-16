import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.security import is_user_allowed
from bot.utils import error_handler
from bot.config import Config

logger = logging.getLogger(__name__)


@error_handler
async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exit the conversation — wave and delete messages."""
    cfg: Config = context.bot_data['config']
    user = update.effective_user
    if not is_user_allowed(user.id, cfg.filtered_users):
        await update.callback_query.answer(
            "⛔️ Доступ запрещён.", show_alert=False
        )
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="👋")
    await asyncio.sleep(1)
    await query.delete_message()
    await context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=context.get_start_message()
    )
    return ConversationHandler.END
