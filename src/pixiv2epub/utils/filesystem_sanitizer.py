# FILE: src/pixiv2epub/utils/filesystem_sanitizer.py

import re
from pathlib import Path
from typing import Any, Dict

# 定数をこのファイル内に配置
INVALID_PATH_CHARS_REGEX = r'[\\/:*?"<>|]'


def sanitize_path_part(part: str, max_length: int) -> str:
    """ファイル/ディレクトリ名として安全でない文字を'_'に置換し、長さを制限します。"""
    # 無効な文字を置換
    sanitized_part = re.sub(INVALID_PATH_CHARS_REGEX, "_", part).strip()

    # 文字数がmax_lengthを超える場合は切り詰める
    if len(sanitized_part) > max_length:
        # ファイル拡張子を保持するために、拡張子とそれ以外を分離
        stem, dot, extension = sanitized_part.rpartition(".")
        if dot:
            # 拡張子の長さを考慮して、ファイル名の本体（stem）を切り詰める
            max_stem_length = max_length - len(dot) - len(extension)
            return f"{stem[:max_stem_length]}.{extension}"
        else:
            return sanitized_part[:max_length]

    return sanitized_part


def generate_sanitized_path(
    template: str, variables: Dict[str, Any], max_length: int
) -> Path:
    """テンプレートと変数から安全なパスを生成します。変数を先にサニタイズします。"""

    # テンプレートに変数を埋め込む前に、各変数の値をサニタイズする
    # これにより、title内の'/'などがパス区切り文字として扱われるのを防ぐ
    safe_vars = {
        key: sanitize_path_part(str(value or ""), max_length=max_length)
        for key, value in variables.items()
    }

    relative_path_str = template.format_map(safe_vars)

    return Path(relative_path_str)
