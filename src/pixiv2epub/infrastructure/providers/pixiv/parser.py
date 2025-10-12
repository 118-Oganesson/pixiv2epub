# FILE: src/pixiv2epub/infrastructure/providers/pixiv/parser.py
import re
from pathlib import Path
from typing import Callable, Dict, List, Tuple, Union

from loguru import logger

from .... import constants as const


class PixivParser:
    """Pixiv独自タグをHTMLに変換するパーサー。"""

    def __init__(self, image_paths: Dict[str, Path]):
        """
        Args:
            image_paths (Dict[str, Path]): 画像IDとローカルファイルパスのマッピング。
        """
        self.image_relative_paths = {
            k: f"../assets/{const.IMAGES_DIR_NAME}/{v.name}"
            for k, v in image_paths.items()
        }

    def _replace_image_tag(self, match: re.Match) -> str:
        """画像タグ `[pixivimage:id]` をHTMLの `<img>` タグに置換します。"""
        tag_type = match.group(1).replace("image", "")
        image_id = match.group(2)
        path = self.image_relative_paths.get(image_id)

        if path:
            return f'<img alt="{tag_type}_{image_id}" src="{path}" />'

        logger.warning(f"置換対象の画像ID '{image_id}' のパスが見つかりませんでした。")
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
        """与えられたテキスト内のPixiv独自タグをHTMLタグに一括で変換します。"""
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
        return match.group(1).strip() if match else f"ページ {page_number}"
