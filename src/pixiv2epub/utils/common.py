# FILE: src/pixiv2epub/utils/common.py
"""
アプリケーション全体で共有される共通のユーティリティ関数。
"""


def get_media_type_from_filename(filename: str) -> str:
    """ファイル名の拡張子からMIMEタイプを返します。"""
    ext = filename.lower().split('.')[-1]
    MEDIA_TYPES = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'svg': 'image/svg+xml',
        'webp': 'image/webp',
        'xhtml': 'application/xhtml+xml',
        'css': 'text/css',
    }
    return MEDIA_TYPES.get(ext, 'application/octet-stream')
