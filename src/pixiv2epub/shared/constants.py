# FILE: src/pixiv2epub/shared/constants.py
import uuid

# --- ワークスペースディレクトリ構造関連 ---
# ダウンロードした画像を格納するディレクトリ名
IMAGES_DIR_NAME = "images"
# 小説の本文(XHTML)やメタデータ(detail.json)を格納するディレクトリ名
SOURCE_DIR_NAME = "source"
# 画像など、ソース以外のすべてのアセットを格納する親ディレクトリ名
ASSETS_DIR_NAME = "assets"
# ワークスペースの状態を記録するマニフェストファイル名
MANIFEST_FILE_NAME = "manifest.json"
# EPUB生成用の正規化されたメタデータを保存するファイル名
DETAIL_FILE_NAME = "detail.json"

# --- EPUB生成関連 ---
# EPUBのブックIDを決定論的に生成するための固定の名前空間UUID
# これにより、同じ作品からは常に同じIDが生成される
NAMESPACE_UUID = uuid.UUID("c22d7879-055f-4203-be9b-7f11e9f23a85")

# EPUBテーマ（テンプレート）のデフォルト名
DEFAULT_THEME_NAME = "default"


# --- 画像ファイル名関連 ---
# 表紙画像のファイル名の基本部分（拡張子なし）
COVER_IMAGE_STEM = "cover"
# 小説の本文中にアップロードされた画像のファイル名プレフィックス
UPLOADED_IMAGE_PREFIX = "uploaded_"
# 本文中で参照されるPixivイラストのファイル名プレフィックス
PIXIV_IMAGE_PREFIX = "pixiv_"
