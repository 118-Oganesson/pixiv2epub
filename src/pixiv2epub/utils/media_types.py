# src/pixiv2epub/utils/media_types.py
"""
ファイル拡張子とMIMEタイプに関連する共有ユーティリティ。
"""
from typing import cast

from ..shared.constants import MIME_TYPES

# マッピングをここで定義して、MIME_TYPES dataclassの属性(UPPERCASE)に合わせる
_EXT_TO_ATTR_MAP = {
    'jpg': 'JPEG',
    'jpeg': 'JPEG',
    'png': 'PNG',
    'gif': 'GIF',
    'svg': 'SVG',
    'webp': 'WEBP',
    'xhtml': 'XHTML',
    'css': 'CSS',
}


def get_media_type_from_filename(filename: str) -> str:
    """ファイル名の拡張子からMIMEタイプを返します。"""
    ext = filename.lower().split('.')[-1]
    attr_name = _EXT_TO_ATTR_MAP.get(ext)

    if attr_name:
        # 'JPEG' などの属性名を使って dataclass から値を取得
        return cast(str, getattr(MIME_TYPES, attr_name))

    # 不明な拡張子はデフォルト値を返す
    return MIME_TYPES.OCTET_STREAM
