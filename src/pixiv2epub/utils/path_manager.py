# src/pixiv2epub/utils/path_manager.py

import re
from pathlib import Path
from typing import Any, Dict

from .. import constants as const


def sanitize_path_part(part: str) -> str:
    """ファイル/ディレクトリ名として安全でない文字を'_'に置換します。"""
    return re.sub(const.INVALID_PATH_CHARS_REGEX, "_", part).strip()


def generate_sanitized_path(template: str, variables: Dict[str, Any]) -> Path:
    """テンプレートと変数からパス文字列を生成し、各部分をサニタイズします。"""
    safe_vars = {k: v or "" for k, v in variables.items()}
    relative_path_str = template.format_map(safe_vars)
    safe_parts = [sanitize_path_part(part) for part in Path(relative_path_str).parts]
    return Path(*safe_parts)
