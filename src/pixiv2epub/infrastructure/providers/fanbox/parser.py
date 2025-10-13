# FILE: src/pixiv2epub/infrastructure/providers/fanbox/parser.py

from pathlib import Path
from typing import Dict, List, Tuple
from html import escape

from loguru import logger

from .... import constants as const
from ....models.fanbox import PostBodyArticle, ParagraphBlock, HeaderBlock, ImageBlock


class FanboxParser:
    """Fanbox APIの本文ブロックをHTMLに変換するパーサー。"""

    def __init__(self, image_paths: Dict[str, Path]):
        """
        Args:
            image_paths (Dict[str, Path]): 画像IDとローカルファイルパスのマッピング。
        """
        self.image_relative_paths = {
            image_id: f"../assets/{const.IMAGES_DIR_NAME}/{file_path.name}"
            for image_id, file_path in image_paths.items()
        }

    def _parse_paragraph_block(self, block: ParagraphBlock) -> str:
        """段落ブロックを解析し、スタイルとリンクを適用したHTMLを返します。"""
        # テキストが空の場合は、改行として<br />を挿入
        if not block.text:
            return "<br />"

        # 元のテキストをエスケープしておく
        text = escape(block.text)

        # 挿入するHTMLタグをリストにまとめる: (index, tag_string)
        tags_to_insert: List[Tuple[int, str]] = []

        # スタイル情報をタグに変換
        if block.styles:
            for style in block.styles:
                # 現在は'bold'のみ対応
                if style.type == "bold":
                    tags_to_insert.append((style.offset, "<b>"))
                    tags_to_insert.append((style.offset + style.length, "</b>"))
                # TODO: 他のスタイル（イタリックなど）が将来追加された場合に対応

        # リンク情報を<a>タグに変換
        if block.links:
            for link in block.links:
                escaped_url = escape(str(link.url))
                tags_to_insert.append((link.offset, f'<a href="{escaped_url}">'))
                tags_to_insert.append((link.offset + link.length, "</a>"))

        # indexの降順（大きい順）でソート
        # これにより、文字列の末尾からタグを挿入でき、前の挿入が後のindexに影響を与えなくなる
        tags_to_insert.sort(key=lambda x: x[0], reverse=True)

        # ソートされたリストを元に、テキストにタグを挿入
        for index, tag in tags_to_insert:
            text = text[:index] + tag + text[index:]

        # 最後に、テキスト内の改行文字を<br />に置換
        return text.replace("\n", "<br />\n")

    def parse(self, body: PostBodyArticle) -> str:
        """本文ブロックのリストを単一のHTML文字列に変換します。"""
        if not hasattr(body, "blocks"):
            logger.warning(
                "本文データに'blocks'が含まれていません。'text'形式の可能性があります。"
            )
            if hasattr(body, "text"):
                return escape(body.text).replace("\n", "<br />\n")
            return ""

        html_parts = []
        for block in body.blocks:
            if isinstance(block, HeaderBlock):
                html_parts.append(f"<h2>{escape(block.text)}</h2>")
            elif isinstance(block, ParagraphBlock):
                html_parts.append(self._parse_paragraph_block(block))
            elif isinstance(block, ImageBlock):
                image_path = self.image_relative_paths.get(block.image_id)
                if image_path:
                    html_parts.append(
                        f'<img src="{image_path}" alt="image_{block.image_id}" />'
                    )
                else:
                    logger.warning(
                        f"画像ID '{block.image_id}' のパスが見つかりませんでした。"
                    )
            # TODO: FileBlockやUrlEmbedBlockなど、他のブロックタイプに対応する処理を実装
            else:
                logger.debug(f"未対応のブロックタイプです: {block.type}")
                html_parts.append("")

        # 各ブロックを単純に連結
        return "\n".join(html_parts)
