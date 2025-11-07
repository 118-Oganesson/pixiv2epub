# src/pixiv2epub/shared/constants.py
import re
from dataclasses import dataclass
from typing import Final


# --- 1. Workspace Structure ---
# (models/workspace.py や repositories/filesystem.py がこれを参照)
@dataclass(frozen=True)
class WorkspacePaths:
    """
    ワークスペースのディレクトリ・ファイル構造を定義する。
    models/workspace.py や repositories/filesystem.py がこれを参照する。
    """

    SOURCE_DIR_NAME: str = 'source'
    ASSETS_DIR_NAME: str = 'assets'
    IMAGES_DIR_NAME: str = 'images'
    MANIFEST_FILE_NAME: str = 'manifest.json'
    DETAIL_FILE_NAME: str = 'detail.json'


WORKSPACE_PATHS: Final = WorkspacePaths()


# --- 2. Mime Types ---
# (utils/media_types.py の移管先)
@dataclass(frozen=True)
class MimeTypes:
    """
    MIMEタイプの中央定義
    """

    JPEG: str = 'image/jpeg'
    PNG: str = 'image/png'
    GIF: str = 'image/gif'
    SVG: str = 'image/svg+xml'  # 元のコードに基づき追加
    WEBP: str = 'image/webp'
    XHTML: str = 'application/xhtml+xml'
    CSS: str = 'text/css'
    EPUB: str = 'application/epub+zip'
    OCTET_STREAM: str = 'application/octet-stream'


MIME_TYPES: Final = MimeTypes()


# --- 3. URL Patterns ---
# (utils/url_parser.py の移管先)
@dataclass(frozen=True)
class Patterns:
    """
    URL解析用のコンパイル済み正規表現
    """

    PIXIV_WORK: re.Pattern = re.compile(r'pixiv\.net/novel/show\.php\?id=(\d+)')
    PIXIV_SERIES: re.Pattern = re.compile(r'pixiv\.net/novel/series/(\d+)')
    PIXIV_CREATOR: re.Pattern = re.compile(r'pixiv\.net/users/(\d+)')
    FANBOX_WORK: re.Pattern = re.compile(r'fanbox\.cc/(?:@[\w\-]+/)?posts/(\d+)')
    FANBOX_CREATOR: re.Pattern = re.compile(
        r'(?:www\.)?fanbox\.cc/@([\w\-]+)|([\w\-]+)\.fanbox\.cc'
    )


PATTERNS: Final = Patterns()


# --- 4. Environment Keys ---
# (cli.py のハードコード値の移管先)
@dataclass(frozen=True)
class EnvKeys:
    """
    Pydantic BaseSettings (settings.py) と連動する環境変数キー。
    """

    _PREFIX: str = 'PIXIV2EPUB_'
    _DELIMITER: str = '__'

    # settings.py の定義から導出
    PIXIV_TOKEN: str = f'{_PREFIX}PROVIDERS{_DELIMITER}PIXIV{_DELIMITER}REFRESH_TOKEN'
    FANBOX_SESSID: str = f'{_PREFIX}PROVIDERS{_DELIMITER}FANBOX{_DELIMITER}SESSID'


ENV_KEYS: Final = EnvKeys()


# --- 5. UI Related ---
@dataclass(frozen=True)
class AssetNames:
    """
    アセットファイル名を管理する
    """

    INJECTOR_SCRIPT: str = 'injector.js'

    COVER_IMAGE_STEM: str = 'cover'
    UPLOADED_IMAGE_PREFIX: str = 'uploaded_'
    PIXIV_IMAGE_PREFIX: str = 'pixiv_'

ASSET_NAMES: Final = AssetNames()
