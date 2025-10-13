# FILE: src/pixiv2epub/infrastructure/providers/fanbox/workspace_writer.py

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Optional, Union
from html import escape

from loguru import logger

from .... import constants as const
from ....models.local import Author, NovelMetadata, PageInfo
from ....models.fanbox import Post, PostBodyArticle, PostBodyText
from ....models.workspace import Workspace, WorkspaceManifest
from .parser import FanboxParser


class FanboxWorkspaceWriter:
    """APIから取得したFanboxのデータを解釈し、ワークスペース内に永続化するクラス。"""

    def __init__(
        self,
        workspace: Workspace,
        cover_path: Optional[Path],
        image_paths: Dict[str, Path],
    ):
        self.workspace = workspace
        self.cover_path = cover_path
        self.image_paths = image_paths
        self.parser = FanboxParser(self.image_paths)

    def persist(
        self,
        post_data: Post,
        manifest_data: WorkspaceManifest,
    ):
        """一連の保存処理を実行するメインメソッド。"""
        logger.debug(f"永続化処理を開始します: {self.workspace.root_path}")
        self._save_manifest(manifest_data)
        parsed_html = self.parser.parse(post_data.body)
        self._save_pages(parsed_html)
        self._save_detail_json(post_data)
        logger.debug("永続化処理が完了しました。")

    def _save_manifest(self, manifest_data: WorkspaceManifest):
        """ワークスペースのマニフェストファイルを保存します。"""
        try:
            with open(self.workspace.manifest_path, "w", encoding="utf-8") as f:
                json.dump(asdict(manifest_data), f, ensure_ascii=False, indent=2)
            logger.debug("manifest.json の保存が完了しました。")
        except IOError as e:
            logger.error(f"manifest.json の保存に失敗しました: {e}")

    def _save_pages(self, parsed_html: str):
        """単一のXHTMLファイルとして保存します。"""
        filename = self.workspace.source_path / "page-1.xhtml"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(parsed_html)
            logger.debug("1ページの保存が完了しました。")
        except IOError as e:
            logger.error(f"ページの保存に失敗しました: {e}")

    def _get_body_text_length(self, body: Union[PostBodyArticle, PostBodyText]) -> int:
        """本文全体の文字数を計算します。"""
        if isinstance(body, PostBodyText):
            return len(body.text or "")
        elif isinstance(body, PostBodyArticle):
            total_len = 0
            for block in body.blocks:
                if hasattr(block, "text"):
                    total_len += len(block.text or "")
            return total_len
        return 0

    def _save_detail_json(self, post_data: Post):
        """投稿のメタデータを抽出し、'detail.json'として保存します。"""
        author_info = Author(name=post_data.user.name, id=int(post_data.user.user_id))
        pages_info = [PageInfo(title="本文", body="./page-1.xhtml")]

        relative_cover_path = (
            f"../{self.workspace.assets_path.name}/{const.IMAGES_DIR_NAME}/{self.cover_path.name}"
            if self.cover_path
            else None
        )

        source_url = (
            f"https://www.fanbox.cc/@{post_data.creator_id}/posts/{post_data.id}"
        )

        parsed_description = ""
        if post_data.excerpt:
            parsed_description = escape(post_data.excerpt).replace("\n", "<br />\n")

        body_text_length = self._get_body_text_length(post_data.body)

        metadata = NovelMetadata(
            title=post_data.title,
            authors=author_info,
            series=None,
            description=parsed_description,
            identifier={"post_id": post_data.id, "creator_id": post_data.creator_id},
            date=post_data.published_datetime,
            cover_path=relative_cover_path,
            tags=post_data.tags,
            original_source=source_url,
            pages=pages_info,
            text_length=body_text_length,
        )

        try:
            metadata_dict = asdict(metadata)
            detail_path = self.workspace.source_path / const.DETAIL_FILE_NAME
            with open(detail_path, "w", encoding="utf-8") as f:
                json.dump(metadata_dict, f, ensure_ascii=False, indent=2)
            logger.debug("detail.json の保存が完了しました。")
        except IOError as e:
            logger.error(f"detail.json の保存に失敗しました: {e}")
