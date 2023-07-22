import os
import telegram
import logging
from dotenv import load_dotenv


dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] - %(message)s',
    level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


# ==========================================================================================


def send_audio(bot: telegram.Bot, audio) -> bool:
    logger.info(f"[send_audio] - Отправка записи: {audio}")
    if isinstance(audio, str):
        print('str')
        try:
            audio = open(audio, "rb")
            bot.send_audio(TELEGRAM_CHAT_ID, audio)
            logger.debug(f"[send_audio] - Запись успешно отправлена - {audio}")
            return True
        except Exception as error:
            logger.error(
                f"[send_audio] - Сбой отправки данных - {audio} - {error}")
        return True
    if isinstance(audio, list):
        try:
            media = [telegram.InputMediaAudio(
                open(url, "rb")) for url in audio]
            response = bot.send_media_group(
                chat_id=TELEGRAM_CHAT_ID,
                media=media,
                disable_notification=True,
                # reply_to_message_id=message.message_id
            )
            logger.debug(
                f"[send_audio] - Записи успешно отправлена - {type(response)}")
            logger.debug(
                f"[send_audio] - Записи успешно отправлена - {response}")
            return response
        except Exception as error:
            logger.error(
                f"[send_audio] - Сбой отправки данных - {audio} - {error}")
        return True
    logger.info("[send_audio] - Нет данных к отправке")
    return False

def get_chunks(path, number=20):
    # получаем список файлов с абсолютным урлом
    for root, _, files in os.walk(os.path.abspath(path)):
        audio_url = []
        for file in files:
            audio_url.append(os.path.join(root, file))
    # делим список на списки по 20 файлов
    return [audio_url[x:x+number] for x in range(0, len(audio_url), number)]

def send_media_group(bot, path="usb_x32"):
    chunks = get_chunks(path)
    for chunk in chunks:
        try:
            audio_message = send_audio(bot, chunk)
            logger.info(f"Отправленно сообщение {audio_message}")
        except Exception as error:
            logger.error(
                Exception,
                f"[main] - Сбой отправки сообщения - {error}",
                exc_info=True
            )

# ==========================================================================================


def main():
    bot = telegram.Bot(token=TELEGRAM_TOKEN)



if __name__ == "__main__":
    main()
