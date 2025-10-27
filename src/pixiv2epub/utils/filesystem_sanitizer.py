# FILE: src/pixiv2epub/utils/filesystem_sanitizer.py

import re
from pathlib import Path
from typing import Any

# 定数をこのファイル内に配置
INVALID_PATH_CHARS_REGEX = r'[\\/:*?"<>|]'


def sanitize_path_part(part: str, max_length: int) -> str:
    """ファイル/ディレクトリ名として安全でない文字を'_'に置換し、長さを制限します。"""
    # 無効な文字を置換
    sanitized_part = re.sub(INVALID_PATH_CHARS_REGEX, '_', part).strip()

    # 文字数がmax_lengthを超える場合は切り詰める
    if len(sanitized_part) <= max_length:
        return sanitized_part

    # pathlibを使用して拡張子を安全に分離
    p = Path(sanitized_part)
    stem = p.stem
    extension = p.suffix  # ".epub" のようにドットを含む

    if extension:
        # 拡張子の長さを考慮して、ファイル名の本体(stem)を切り詰める
        max_stem_length = max_length - len(extension)
        if len(stem) > max_stem_length:
            stem = stem[:max_stem_length]
        return f'{stem}{extension}'
    else:
        # 拡張子がない場合
        return sanitized_part[:max_length]


def generate_sanitized_path(
    template: str, variables: dict[str, Any], max_length: int
) -> Path:
    """テンプレートと変数から安全なパスを生成します。変数を先にサニタイズします。"""

    # テンプレートに変数を埋め込む前に、各変数の値をサニタイズする
    # これにより、title内の'/'などがパス区切り文字として扱われるのを防ぐ
    safe_vars = {
        key: sanitize_path_part(str(value or ''), max_length=max_length)
        for key, value in variables.items()
    }

    relative_path_str = template.format_map(safe_vars)

    return Path(relative_path_str)
