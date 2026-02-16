# Conversation stages
START_ROUTES, END_ROUTES = range(2)

# Callback data — named constants instead of numeric ONE/TWO/THREE
CB_FILE_LIST = "cb_file_list"
CB_EXIT = "cb_exit"
CB_DOWNLOAD_ALL = "cb_download_all"
CB_SELECT_FILE = "cb_select_file"

# Pagination
CB_NEXT_PAGE = "next_page"
CB_PREV_PAGE = "prev_page"
CB_SIX_NEXT_PAGE = "six_next_page"
CB_SIX_PREV_PAGE = "six_prev_page"

# Date downloads
CB_DOWNLOAD_TODAY = "download_today"
CB_DOWNLOAD_LAST_SUNDAY = "download_last_sunday"

# File download prefix
CB_FILE_PREFIX = "file_to_download:"

# Archive reassembly instructions (shared between send_file_to_user and send_files_group)
ARCHIVE_INSTRUCTIONS = (
    "<b>Загрузка завершена!</b>\n"
    "<i>Если архив был разбит на части, скачайте все части в одну папку.</i>\n\n"
    "<b>Инструкция по склейке и распаковке:</b>\n"
    "<pre>\n"
    "<b>Linux/macOS:</b>\n"
    "<code>cat archive.zip.part* > archive.zip\nunzip archive.zip</code>\n\n"
    "<b>Windows (PowerShell):</b>\n"
    "<code>Get-Content archive.zip.part* -Encoding Byte -ReadCount 0 "
    "| Set-Content archive.zip -Encoding Byte\n"
    "Expand-Archive archive.zip</code>\n\n"
    "<b>Windows (cmd):</b>\n"
    "<code>copy /b archive.zip.part* archive.zip</code>\n\n"
    "<b>Python:</b>\n"
    "<code>python -c \"with open('archive.zip','wb') as w: i=0\n"
    "while True:\n"
    " f='archive.zip.part'+str(i)\n"
    " if not __import__('os').path.exists(f): break\n"
    " w.write(open(f,'rb').read()); i+=1\"\n"
    "unzip archive.zip</code>\n"
    "</pre>"
)

# Audio extensions for sending as audio message
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.m4a'}
