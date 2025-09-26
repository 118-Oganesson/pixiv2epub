# src/pixiv2epub/utils/url_parser.py

import re
from typing import Tuple

from ..core.exceptions import InvalidInputError

URL_PATTERNS = {
    "novel": re.compile(r"pixiv\.net/novel/show\.php\?id=(\d+)"),
    "series": re.compile(r"pixiv\.net/novel/series/(\d+)"),
    "user": re.compile(r"pixiv\.net/users/(\d+)"),
}


def parse_input(input_str: str) -> Tuple[str, int]:
    """入力された文字列 (URLまたはID) を解析し、対象のタイプとIDを返します。"""
    for target_type, pattern in URL_PATTERNS.items():
        if match := pattern.search(input_str):
            return target_type, int(match.group(1))

    try:
        novel_id = int(input_str)
        if novel_id > 0:
            return "novel", novel_id
    except (ValueError, TypeError):
        pass

    raise InvalidInputError(f"無効なURLまたはIDです: '{input_str}'")
