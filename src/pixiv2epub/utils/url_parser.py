# FILE: src/pixiv2epub/utils/url_parser.py
import re
from typing import Tuple, Union

from ..shared.exceptions import InvalidInputError

URL_PATTERNS = {
    "pixiv_novel": re.compile(r"pixiv\.net/novel/show\.php\?id=(\d+)"),
    "pixiv_series": re.compile(r"pixiv\.net/novel/series/(\d+)"),
    "pixiv_user": re.compile(r"pixiv\.net/users/(\d+)"),
    "fanbox_post": re.compile(r"fanbox\.cc/(?:@[\w\-]+/)?posts/(\d+)"),
    "fanbox_creator": re.compile(
        r"(?:www\.)?fanbox\.cc/@([\w\-]+)|([\w\-]+)\.fanbox\.cc"
    ),
}


def parse_input(input_str: str) -> Tuple[str, Union[int, str]]:
    """入力された文字列 (URL) を解析し、対象のタイプとIDを返します。"""
    for target_type, pattern in URL_PATTERNS.items():
        if match := pattern.search(input_str):
            if target_type == "fanbox_creator":
                # fanbox_creatorは2つのキャプチャグループを持つ
                creator_id = next((g for g in match.groups() if g is not None), None)
                if creator_id:
                    return target_type, creator_id
            else:
                return target_type, int(match.group(1))

    raise InvalidInputError(f"無効なURLです: '{input_str}'")
