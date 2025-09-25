# src/pixiv2epub/utils/url_parser.py

import re
from typing import Tuple

from ..exceptions import InvalidInputError

URL_PATTERNS = {
    "novel": re.compile(r"pixiv\.net/novel/show\.php\?id=(\d+)"),
    "series": re.compile(r"pixiv\.net/novel/series/(\d+)"),
    "user": re.compile(r"pixiv\.net/users/(\d+)"),
}


def parse_input(input_str: str) -> Tuple[str, int]:
    """
    入力された文字列 (URLまたはID) を解析し、
    対象のタイプとIDを返します。

    Args:
        input_str (str): Pixivの小説、シリーズ、ユーザーのURLまたはID。

    Returns:
        Tuple[str, int]: ("novel" | "series" | "user", id) のタプル。

    Raises:
        InvalidInputError: 入力文字列がどのパターンにも一致しない場合。
    """
    for target_type, pattern in URL_PATTERNS.items():
        match = pattern.search(input_str)
        if match:
            return target_type, int(match.group(1))

    # URLでない場合は、単純なIDとして解釈を試みる
    # ここでは小説IDであると仮定するが、将来的にはより高度な判定も可能
    try:
        novel_id = int(input_str)
        # 簡単なバリデーション（例：IDは正の整数）
        if novel_id > 0:
            return "novel", novel_id
    except (ValueError, TypeError):
        pass

    raise InvalidInputError(f"無効なURLまたはIDです: '{input_str}'")
