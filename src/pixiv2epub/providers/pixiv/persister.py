# src/pixiv2epub/providers/pixiv/persister.py

import json
import logging
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from ... import constants as const
from ...models.local import Author, NovelMetadata, PageInfo, SeriesInfo
from ...models.pixiv import NovelApiResponse
from ...utils.path_manager import PathManager
from .parser import PixivParser


class PixivDataPersister:
    """APIから取得したデータを解釈し、ローカルファイルに永続化するクラス。"""

    def __init__(
        self,
        paths: PathManager,
        cover_path: Optional[Path],
        image_paths: Dict[str, Path],
    ):
        """
        Args:
            paths (PathManager): ファイルパスを管理するインスタンス。
            cover_path (Optional[Path]): ダウンロード済みの表紙画像のパス。
            image_paths (Dict[str, Path]): ダウンロード済みの埋め込み画像のパス。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.paths = paths
        self.cover_path = cover_path
        self.image_paths = image_paths
        self.parser = PixivParser(self.image_paths)

    def persist(self, novel_data: NovelApiResponse, detail_data_dict: dict):
        """一連の保存処理を実行するメインメソッド。"""
        self.logger.debug(f"永続化処理を開始します: {self.paths.novel_dir}")

        # 1. 本文をパース・保存
        parsed_text = self.parser.parse(novel_data.text)
        self._save_pages(parsed_text)

        # 2. メタデータを構築・保存
        parsed_description = self.parser.parse(
            detail_data_dict.get("novel", {}).get("caption", "")
        )
        self._save_detail_json(
            novel_data, detail_data_dict, parsed_text, parsed_description
        )

        self.logger.debug("永続化処理が完了しました。")

    def _save_pages(self, parsed_text: str):
        """小説本文をページごとに分割し、XHTMLファイルとして保存します。"""
        pages = parsed_text.split("[newpage]")
        for i, page_content in enumerate(pages):
            filename = self.paths.page_path(i + 1)
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

        formatted_date = ""
        if raw_date := novel.get("create_date"):
            try:
                dt_object = datetime.fromisoformat(raw_date)
                formatted_date = dt_object.strftime("%Y年%m月%d日 %H:%M")
            except (ValueError, TypeError):
                formatted_date = raw_date

        author_info = Author(
            name=novel.get("user", {}).get("name"), id=novel.get("user", {}).get("id")
        )
        pages_info = [
            PageInfo(
                title=self.parser.extract_page_title(content, i + 1),
                body=f"./page-{i + 1}.xhtml",
            )
            for i, content in enumerate(pages_content)
        ]
        series_info = SeriesInfo.from_dict(novel.get("series"))

        # cover_pathは絶対パスなので、detail.jsonに保存する際は相対パスに変換
        relative_cover_path = (
            f"./{const.IMAGES_DIR_NAME}/{self.cover_path.name}"
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
                "uuid": f"urn:uuid:{uuid.uuid4()}",
            },
            date=formatted_date,
            cover_path=relative_cover_path,
            tags=[t.get("name") for t in novel.get("tags", [])],
            original_source=const.PIXIV_NOVEL_URL.format(novel_id=novel.get("id")),
            pages=pages_info,
            text_length=novel.get("text_length"),
        )

        try:
            metadata_dict = asdict(metadata)
            with open(self.paths.detail_json_path, "w", encoding="utf-8") as f:
                json.dump(metadata_dict, f, ensure_ascii=False, indent=2)
            self.logger.debug("detail.json の保存が完了しました。")
        except IOError as e:
            self.logger.error(f"detail.json の保存に失敗しました: {e}")
