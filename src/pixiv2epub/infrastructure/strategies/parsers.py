# FILE: src/pixiv2epub/infrastructure/strategies/parsers.py
import re
from html import escape
from pathlib import Path
from typing import Callable, Dict, List, Tuple, Union

from loguru import logger

from ... import constants as const
from ...models.fanbox import (
    HeaderBlock,
    ImageBlock,
    ParagraphBlock,
    PostBodyArticle,
)
from .interfaces import IContentParser


class PixivTagParser(IContentParser):
    """Pixivの独自タグ `[tag]` をHTMLに変換するパーサー。"""

    def parse(self, raw_content: str, image_paths: Dict[str, Path]) -> str:
        self.image_relative_paths = {
            image_id: f"../assets/{const.IMAGES_DIR_NAME}/{file_path.name}"
            for image_id, file_path in image_paths.items()
        }
        text = raw_content
        if not text:
            return ""

        strategies = self._get_replacement_strategies()
        for pattern, replacement in strategies:
            text = pattern.sub(replacement, text)
        return text.replace("\n", "<br />\n")

    def _replace_image_tag(self, match: re.Match) -> str:
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

    @staticmethod
    def extract_page_title(page_content: str, page_number: int) -> str:
        match = re.search(r"<h2>(.*?)</h2>", page_content)
        return match.group(1).strip() if match else f"ページ {page_number}"


class FanboxBlockParser(IContentParser):
    """Fanboxの本文ブロック（JSON）をHTMLに変換するパーサー。"""

    def parse(self, raw_content: PostBodyArticle, image_paths: Dict[str, Path]) -> str:
        self.image_relative_paths = {
            image_id: f"../assets/{const.IMAGES_DIR_NAME}/{file_path.name}"
            for image_id, file_path in image_paths.items()
        }
        body = raw_content

        if not hasattr(body, "blocks"):
            if hasattr(body, "text"):
                return escape(body.text).replace("\n", "<br />\n")
            return ""

        final_html_parts = []
        num_blocks = len(body.blocks)

        for i, block in enumerate(body.blocks):
            part = ""
            if isinstance(block, HeaderBlock):
                part = f"<h2>{escape(block.text)}</h2>"
            elif isinstance(block, ParagraphBlock):
                part = self._parse_paragraph_block(block)
            elif isinstance(block, ImageBlock):
                image_path = self.image_relative_paths.get(block.image_id)
                if image_path:
                    part = f'<img src="{image_path}" alt="image_{block.image_id}" />'
                else:
                    logger.warning(
                        f"画像ID '{block.image_id}' のパスが見つかりませんでした。"
                    )
            else:
                block_type = getattr(block, "type", "unknown")
                logger.warning(
                    f"未対応のFanboxブロックタイプを検出しました: {block_type}"
                )
                # ユーザーにフィードバックするためのプレースホルダーを生成
                part = (
                    f'<div style="padding: 1em; margin: 1em 0; border: 1px dashed #ccc; color: #777; font-style: italic;">'
                    f"サポートされていないコンテンツブロック（タイプ: {escape(str(block_type))}）は表示できません。"
                    f"</div>"
                )

            if part:  # 空のpartは追加しない
                final_html_parts.append(part)

            # 区切り文字の<br />を、条件付きで追加する
            is_last_block = i == num_blocks - 1
            # 現在のブロックが改行そのものではなく、かつ最後のブロックでもない場合のみ区切り文字を追加
            if part != "<br />" and not is_last_block:
                final_html_parts.append("<br />")

        return "\n".join(final_html_parts)

    def _parse_paragraph_block(self, block: ParagraphBlock) -> str:
        # 空のpタグは、単一の改行として機能させる
        if not block.text:
            return "<br />"

        text = escape(block.text)
        tags_to_insert: List[Tuple[int, str]] = []

        if block.styles:
            for style in block.styles:
                if style.type == "bold":
                    tags_to_insert.append((style.offset, "<b>"))
                    tags_to_insert.append((style.offset + style.length, "</b>"))
        if block.links:
            for link in block.links:
                escaped_url = escape(str(link.url))
                tags_to_insert.append((link.offset, f'<a href="{escaped_url}">'))
                tags_to_insert.append((link.offset + link.length, "</a>"))

        tags_to_insert.sort(key=lambda x: x[0], reverse=True)
        for index, tag in tags_to_insert:
            text = text[:index] + tag + text[index:]
        return text.replace("\n", "<br />")
