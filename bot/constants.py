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

# Audio extensions for sending as audio message
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.m4a'}
