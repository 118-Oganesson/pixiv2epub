#
# -----------------------------------------------------------------------------
# pixiv2epub/src/pixiv2epub/constants.py
#
# このモジュールは、アプリケーション全体で使用される定数を定義します。
# URL、ファイルパス、設定キーなどのハードコードされた値を一元管理することで、
# 保守性と一貫性を向上させます。
# -----------------------------------------------------------------------------

# --- URL Templates ---
PIXIV_NOVEL_URL = "https://www.pixiv.net/novel/show.php?id={novel_id}"
PIXIV_ARTWORK_URL = "https://www.pixiv.net/artworks/{illust_id}"

# --- File and Directory Names ---
DEFAULT_RAW_DATA_DIR = "./pixiv_raw"
DEFAULT_EPUB_OUTPUT_DIR = "./epubs"
IMAGES_DIR_NAME = "images"
DETAIL_FILE_NAME = "detail.json"
UNKNOWN_NOVEL_DIR = "novel_unknown"

# --- Regular Expressions ---
# OSのファイル/ディレクトリ名として使用できない文字を検出するための正規表現
INVALID_PATH_CHARS_REGEX = r'[\\/:*?"<>|]'

# --- Default Configuration Templates ---
DEFAULT_NOVEL_DIR_TEMPLATE = "{author_name}/{title}"
DEFAULT_SERIES_DIR_TEMPLATE = "{author_name}/{title}"
DEFAULT_SERIES_NOVEL_DIR_TEMPLATE = "{title}"
DEFAULT_EPUB_FILENAME_TEMPLATE = "{author_name}/{title}.epub"
DEFAULT_SERIES_EPUB_FILENAME_TEMPLATE = (
    "{author_name}/{series_title}/{title}.epub"
)

# --- Default API Settings ---
DEFAULT_API_DELAY = 1.0
DEFAULT_API_RETRIES = 3

# --- Configuration Keys (for config.toml) ---
# これらのキーは、設定ファイル(config.toml)の構造に対応します。
# タイプミスを防ぎ、IDEの補完を効かせるために定数として定義します。
# [downloader]
KEY_DOWNLOADER = "downloader"
KEY_SAVE_DIRECTORY = "save_directory"
KEY_API_DELAY = "api_delay"
KEY_API_RETRIES = "api_retries"
KEY_OVERWRITE_IMAGES = "overwrite_existing_images"
KEY_RAW_DIR_TEMPLATE = "raw_dir_template"
KEY_SERIES_DIR_TEMPLATE = "series_dir_template"

# [builder]
KEY_BUILDER = "builder"
KEY_OUTPUT_DIRECTORY = "output_directory"
KEY_FILENAME_TEMPLATE = "filename_template"
KEY_SERIES_FILENAME_TEMPLATE = "series_filename_template"
KEY_CSS_FILE = "css_file"
KEY_CLEANUP_AFTER_BUILD = "cleanup_after_build"

# [auth]
KEY_AUTH = "auth"
KEY_REFRESH_TOKEN = "refresh_token"
