# FILE: src/pixiv2epub/infrastructure/strategies/parsers.py

import re
from collections.abc import Callable
from html import escape
from pathlib import Path

from loguru import logger

from ...models.fanbox import (
    HeaderBlock,
    ImageBlock,
    ParagraphBlock,
    PostBodyArticle,
    PostBodyText,
)
from ...shared.constants import WORKSPACE_PATHS
from ..providers.pixiv.constants import PIXIV_ARTWORK_URL, PIXIV_NOVEL_URL
from .interfaces import IContentParser


class PixivTagParser(IContentParser):
    """Pixivの独自タグ `[tag]` をHTMLに変換するパーサー。"""

    def __init__(self) -> None:
        self.image_relative_paths: dict[str, str] = {}

    def parse(self, raw_content: object, image_paths: dict[str, Path]) -> str:
        self.image_relative_paths = {
            image_id: f'../assets/{WORKSPACE_PATHS.IMAGES_DIR_NAME}/{file_path.name}'
            for image_id, file_path in image_paths.items()
        }
        if not isinstance(raw_content, str):
            logger.warning(
                f'PixivTagParserにstr以外の値が渡されました: {type(raw_content)}'
            )
            return ''

        text = raw_content
        if not text:
            return ''

        strategies = self._get_replacement_strategies()
        for pattern, replacement in strategies:
            text = pattern.sub(replacement, text)
        return text.replace('\n', '<br />\n')

    def _replace_image_tag(self, match: re.Match[str]) -> str:
        tag_type = match.group(1).replace('image', '')
        image_id = match.group(2)
        path = self.image_relative_paths.get(image_id)
        if path:
            return f'<img alt="{tag_type}_{image_id}" src="{path}" />'
        logger.warning(f"置換対象の画像ID '{image_id}' のパスが見つかりませんでした。")
        return match.group(0)

    def _get_replacement_strategies(
        self,
    ) -> list[tuple[re.Pattern[str], str | Callable[[re.Match[str]], str]]]:
        return [
            (
                re.compile(r'\[(uploadedimage|pixivimage):(\d+)\]'),
                self._replace_image_tag,
            ),
            (re.compile(r'\[jump:(\d+)\]'), r'<a href="page-\1.xhtml">\1ページへ</a>'),
            (re.compile(r'\[chapter:(.+?)\]'), r'<h2>\1</h2>'),
            (
                re.compile(r'\[\[rb:(.+?)\s*>\s*(.+?)\]\]'),
                r'<ruby>\1<rt>\2</rt></ruby>',
            ),
            (
                re.compile(r'\[\[jumpuri:(.+?)\s*>\s*(https?://.+?)\]\]'),
                r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
            ),
            (
                re.compile(r'pixiv://novels/(\d+)'),
                PIXIV_NOVEL_URL.replace('{novel_id}', r'\1'),
            ),
            (
                re.compile(r'pixiv://illusts/(\d+)'),
                PIXIV_ARTWORK_URL.replace('{illust_id}', r'\1'),
            ),
        ]

    @staticmethod
    def extract_page_title(page_content: str, page_number: int) -> str:
        match = re.search(r'<h2>(.*?)</h2>', page_content)
        return match.group(1).strip() if match else f'ページ {page_number}'


class FanboxBlockParser(IContentParser):
    """Fanboxの本文ブロック(JSON)をHTMLに変換するパーサー。"""

    def __init__(self) -> None:
        self.image_relative_paths: dict[str, str] = {}

    def parse(self, raw_content: object, image_paths: dict[str, Path]) -> str:
        self.image_relative_paths = {
            image_id: f'../assets/{WORKSPACE_PATHS.IMAGES_DIR_NAME}/{file_path.name}'
            for image_id, file_path in image_paths.items()
        }

        if isinstance(raw_content, PostBodyArticle):
            body = raw_content
            if not hasattr(body, 'blocks'):
                return ''

            final_html_parts = []
            num_blocks = len(body.blocks)

            for i, block in enumerate(body.blocks):
                part = ''
                if isinstance(block, HeaderBlock):
                    part = f'<h2>{escape(block.text)}</h2>'
                elif isinstance(block, ParagraphBlock):
                    part = self._parse_paragraph_block(block)
                elif isinstance(block, ImageBlock):
                    image_path = self.image_relative_paths.get(block.image_id)
                    if image_path:
                        part = (
                            f'<img src="{image_path}" alt="image_{block.image_id}" />'
                        )
                    else:
                        logger.warning(
                            f"画像ID '{block.image_id}' のパスが見つかりませんでした。"
                        )
                else:
                    block_type = getattr(block, 'type', 'unknown')
                    logger.warning(
                        f'未対応のFanboxブロックタイプを検出しました: {block_type}'
                    )
                    part = (
                        f'<div style="padding: 1em; margin: 1em 0; border: 1px dashed #ccc; color: #777; font-style: italic;">'
                        f'サポートされていないコンテンツブロック(タイプ: {escape(str(block_type))})は表示できません。'
                        f'</div>'
                    )

                if part:
                    final_html_parts.append(part)

                is_last_block = i == num_blocks - 1
                if part != '<br />' and not is_last_block:
                    final_html_parts.append('<br />')

            return '\n'.join(final_html_parts)

        elif isinstance(raw_content, PostBodyText):
            text_body = raw_content
            return escape(text_body.text or '').replace('\n', '<br />')

        logger.warning(
            f'FanboxBlockParserに予期せぬ型が渡されました: {type(raw_content)}'
        )
        return ''

    def _parse_paragraph_block(self, block: ParagraphBlock) -> str:
        if not block.text:
            return '<br />'

        text = escape(block.text)
        tags_to_insert: list[tuple[int, str]] = []

        if block.styles:
            for style in block.styles:
                if style.type == 'bold':
                    tags_to_insert.append((style.offset, '<b>'))
                    tags_to_insert.append((style.offset + style.length, '</b>'))
        if block.links:
            for link in block.links:
                escaped_url = escape(str(link.url))
                tags_to_insert.append((link.offset, f'<a href="{escaped_url}">'))
                tags_to_insert.append((link.offset + link.length, '</a>'))

        tags_to_insert.sort(key=lambda x: x[0], reverse=True)
        for index, tag in tags_to_insert:
            text = text[:index] + tag + text[index:]
        return text.replace('\n', '<br />')
