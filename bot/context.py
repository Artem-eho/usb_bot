from typing import Optional
from telegram.ext import Application, CallbackContext


class ChatData:
    """Custom class for storing per-chat data."""

    def __init__(self) -> None:
        self.start_message: Optional[int] = None


class CustomContext(CallbackContext):
    """Custom context class with start_message tracking."""

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

    def get_start_message(self) -> Optional[int]:
        return self.chat_data.start_message
