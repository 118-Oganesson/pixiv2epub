# src/pixiv2epub/providers/pixiv/persister.py

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Optional

from ... import constants as const
from ...models.local import Author, NovelMetadata, PageInfo, SeriesInfo
from ...models.pixiv import NovelApiResponse
from ...models.workspace import Workspace, WorkspaceManifest
from .parser import PixivParser


class PixivDataPersister:
    """APIから取得したデータを解釈し、ワークスペース内に永続化するクラス。"""

    def __init__(
        self,
        workspace: Workspace,
        cover_path: Optional[Path],
        image_paths: Dict[str, Path],
    ):
        """
        Args:
            workspace (Workspace): データ保存先のワークスペース。
            cover_path (Optional[Path]): ダウンロード済みの表紙画像のパス。
            image_paths (Dict[str, Path]): ダウンロード済みの埋め込み画像のパス。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.workspace = workspace
        self.cover_path = cover_path
        self.image_paths = image_paths
        self.parser = PixivParser(self.image_paths)

    def persist(
        self,
        novel_data: NovelApiResponse,
        detail_data_dict: dict,
        manifest_data: WorkspaceManifest,
    ):
        """一連の保存処理を実行するメインメソッド。"""
        self.logger.debug(f"永続化処理を開始します: {self.workspace.root_path}")

        # 1. manifest.json を保存
        self._save_manifest(manifest_data)

        # 2. 本文をパース・保存
        parsed_text = self.parser.parse(novel_data.text)
        self._save_pages(parsed_text)

        # 3. メタデータ (detail.json) を構築・保存
        parsed_description = self.parser.parse(
            detail_data_dict.get("novel", {}).get("caption", "")
        )
        self._save_detail_json(
            novel_data, detail_data_dict, parsed_text, parsed_description
        )

        self.logger.debug("永続化処理が完了しました。")

    def _save_manifest(self, manifest_data: WorkspaceManifest):
        """ワークスペースのマニフェストファイルを保存します。"""
        try:
            with open(self.workspace.manifest_path, "w", encoding="utf-8") as f:
                json.dump(asdict(manifest_data), f, ensure_ascii=False, indent=2)
            self.logger.debug("manifest.json の保存が完了しました。")
        except IOError as e:
            self.logger.error(f"manifest.json の保存に失敗しました: {e}")

    def _save_pages(self, parsed_text: str):
        """小説本文をページごとに分割し、XHTMLファイルとして保存します。"""
        pages = parsed_text.split("[newpage]")
        for i, page_content in enumerate(pages):
            filename = self.workspace.source_path / f"page-{i + 1}.xhtml"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page_content)
            except IOError as e:
                self.logger.error(f"ページ {i + 1} の保存に失敗しました: {e}")
        self.logger.debug(f"{len(pages)}ページの保存が完了しました。")

    def _save_detail_json(
        self,
        novel_data: NovelApiResponse,
        detail_data_dict: dict,
        parsed_text: str,
        parsed_description: str,
    ):
        """小説のメタデータを抽出し、'detail.json'として保存します。"""
        novel = detail_data_dict.get("novel", {})
        pages_content = parsed_text.split("[newpage]")

        author_info = Author(
            name=novel.get("user", {}).get("name"), id=novel.get("user", {}).get("id")
        )
        pages_info = [
            PageInfo(
                title=PixivParser.extract_page_title(content, i + 1),
                body=f"./page-{i + 1}.xhtml",
            )
            for i, content in enumerate(pages_content)
        ]

        series_order: Optional[int] = None
        if novel_data.seriesId and novel_data.seriesNavigation:
            nav = novel_data.seriesNavigation
            if nav.prevNovel and nav.prevNovel.contentOrder:
                series_order = int(nav.prevNovel.contentOrder) + 1
            elif nav.nextNovel:  # prevNovelがなくnextNovelがある場合 -> 1番目
                series_order = 1
            else:  # prevNovelもnextNovelもない場合 -> シリーズに1作品のみ
                series_order = 1

        series_info_dict = novel.get("series")
        if series_info_dict and series_order:
            series_info_dict["order"] = series_order

        series_info = SeriesInfo.from_dict(series_info_dict)

        # cover_pathは絶対パスなので、detail.jsonに保存する際は相対パスに変換
        relative_cover_path = (
            f"../{self.workspace.assets_path.name}/{const.IMAGES_DIR_NAME}/{self.cover_path.name}"
            if self.cover_path
            else None
        )

        metadata = NovelMetadata(
            title=novel.get("title"),
            authors=author_info,
            series=series_info,
            description=parsed_description,
            identifier={
                "novel_id": novel.get("id"),
            },
            date=novel.get("create_date"),
            cover_path=relative_cover_path,
            tags=[t.get("name") for t in novel.get("tags", [])],
            original_source=const.PIXIV_NOVEL_URL.format(novel_id=novel.get("id")),
            pages=pages_info,
            text_length=novel.get("text_length"),
        )

        try:
            metadata_dict = asdict(metadata)
            detail_path = self.workspace.source_path / const.DETAIL_FILE_NAME
            with open(detail_path, "w", encoding="utf-8") as f:
                json.dump(metadata_dict, f, ensure_ascii=False, indent=2)
            self.logger.debug("detail.json の保存が完了しました。")
        except IOError as e:
            self.logger.error(f"detail.json の保存に失敗しました: {e}")
