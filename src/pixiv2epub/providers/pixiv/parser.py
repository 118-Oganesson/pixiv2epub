#
# -----------------------------------------------------------------------------
# pixiv2epub/src/pixiv2epub/providers/pixiv/parser.py
#
# Pixivの小説本文やキャプションに含まれる独自タグを解析し、
# 標準的なHTMLに変換する責務を持ちます。
# -----------------------------------------------------------------------------

import logging
import re
from typing import Callable, Dict, List, Tuple, Union

from ... import constants as const


class PixivParser:
    """Pixiv独自タグをHTMLに変換するパーサー。"""

    def __init__(self, image_paths: Dict[str, str]):
        """
        PixivParserを初期化します。

        Args:
            image_paths (Dict[str, str]): 画像IDとローカルパスのマッピング。
                                          `[pixivimage:id]` タグの置換に使用します。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.image_paths = image_paths

    def _replace_image_tag(self, match: re.Match) -> str:
        """画像タグ `[pixivimage:id]` をHTMLの `<img>` タグに置換します。"""
        tag_type = match.group(1).replace("image", "")
        image_id = match.group(2)
        path = self.image_paths.get(image_id)

        if path:
            return f'<img alt="{tag_type}_{image_id}" src="{path}" />'

        self.logger.warning(
            f"置換対象の画像ID '{image_id}' のパスが見つかりませんでした。"
        )
        return match.group(0)

    def _get_replacement_strategies(
        self,
    ) -> List[Tuple[re.Pattern, Union[str, Callable]]]:
        """置換ルールのリストを返します。"""
        return [
            (
                re.compile(r"\[(uploadedimage|pixivimage):(\d+)\]"),
                self._replace_image_tag,
            ),
            (re.compile(r"\[jump:(\d+)\]"), r'<a href="page-\1.xhtml">\1ページへ</a>'),
            (re.compile(r"\[chapter:(.+?)\]"), r"<h2>\1</h2>"),
            (
                re.compile(r"\[\[rb:(.+?)\s*>\s*(.+?)\]\]"),
                r"<ruby>\1<rt>\2</rt></ruby>",
            ),
            (
                re.compile(r"\[\[jumpuri:(.+?)\s*>\s*(https?://.+?)\]\]"),
                r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
            ),
            (
                re.compile(r"pixiv://novels/(\d+)"),
                const.PIXIV_NOVEL_URL.replace("{novel_id}", r"\1"),
            ),
            (
                re.compile(r"pixiv://illusts/(\d+)"),
                const.PIXIV_ARTWORK_URL.replace("{illust_id}", r"\1"),
            ),
        ]

    def parse(self, text: str) -> str:
        """
        与えられたテキスト内のPixiv独自タグをHTMLタグに一括で変換します。

        Args:
            text (str): 変換対象のテキスト（小説本文やキャプション）。

        Returns:
            str: HTMLに変換されたテキスト。
        """
        if not text:
            return ""

        strategies = self._get_replacement_strategies()
        for pattern, replacement in strategies:
            text = pattern.sub(replacement, text)

        return text.replace("\n", "<br />\n")

    @staticmethod
    def extract_page_title(page_content: str, page_number: int) -> str:
        """ページ内容から章タイトル(h2)を抽出し、なければデフォルト名を返します。"""
        match = re.search(r"<h2>(.*?)</h2>", page_content)
        return match.group(1) if match else f"ページ {page_number}"
