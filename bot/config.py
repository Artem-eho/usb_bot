import os
from dataclasses import dataclass, field
from dotenv import load_dotenv


@dataclass
class Config:
    telegram_token: str
    mount_path: str
    telegram_chat_id: str = ""
    filtered_users: list = field(default_factory=list)
    file_server_port: int = 8080
    file_server_public_url: str = ""
    file_server_token_ttl: int = 3600
    max_file_size: int = 48 * 1024 * 1024
    page_size: int = 10
    six_files_page_size: int = 8
    menu_lifetime_seconds: int = 15 * 60
    archive_semaphore_limit: int = 20


def load_config() -> Config:
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)

    telegram_token = os.getenv('TELEGRAM_TOKEN', '')
    mount_path = os.getenv('MOUNT_PATH', '')

    if not telegram_token:
        raise RuntimeError(
            "Отсутствуют обязательные переменные окружения: TELEGRAM_TOKEN"
        )
    if not mount_path:
        raise RuntimeError(
            "Отсутствуют обязательные переменные окружения: MOUNT_PATH"
        )

    filtered = os.getenv('FILTERED_USERS', '')
    filtered_users = (
        [u.strip() for u in filtered.split(",") if u.strip()]
        if filtered else []
    )

    return Config(
        telegram_token=telegram_token,
        mount_path=mount_path,
        telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID', ''),
        filtered_users=filtered_users,
        file_server_port=int(os.getenv('FILE_SERVER_PORT', '8080')),
        file_server_public_url=os.getenv('FILE_SERVER_PUBLIC_URL', '').strip('\'" '),
        file_server_token_ttl=int(os.getenv('FILE_SERVER_TOKEN_TTL', '3600')),
    )
