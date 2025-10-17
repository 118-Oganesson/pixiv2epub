# FILE: src/pixiv2epub/shared/constants.py
import uuid

IMAGES_DIR_NAME = "images"
SOURCE_DIR_NAME = "source"
ASSETS_DIR_NAME = "assets"
MANIFEST_FILE_NAME = "manifest.json"
DETAIL_FILE_NAME = "detail.json"

CONTENT_HASH_KEY = "content_hash"

# 決定論的なブックIDを生成するための固定の名前空間UUID
NAMESPACE_UUID = uuid.UUID("c22d7879-055f-4203-be9b-7f11e9f23a85")

# EPUBテーマのデフォルト名
DEFAULT_THEME_NAME = "default"

# 画像ファイル名のプレフィックス/ステム
COVER_IMAGE_STEM = "cover"
UPLOADED_IMAGE_PREFIX = "uploaded_"
PIXIV_IMAGE_PREFIX = "pixiv_"
