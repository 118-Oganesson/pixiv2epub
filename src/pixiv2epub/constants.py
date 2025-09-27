# src/pixiv2epub/constants.py
#
# このモジュールは、アプリケーション全体で使用される不変の定数を定義します。
# URL、固定のファイル名、正規表現などを一元管理します。

# --- URL Templates ---
PIXIV_NOVEL_URL = "https://www.pixiv.net/novel/show.php?id={novel_id}"
PIXIV_ARTWORK_URL = "https://www.pixiv.net/artworks/{illust_id}"

# --- File and Directory Names ---
IMAGES_DIR_NAME = "images"
DETAIL_FILE_NAME = "detail.json"

# --- Regular Expressions ---
# OSのファイル/ディレクトリ名として使用できない文字を検出するための正規表現
INVALID_PATH_CHARS_REGEX = r'[\\/:*?"<>|]'
