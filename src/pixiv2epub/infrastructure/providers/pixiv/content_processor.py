# FILE: src/pixiv2epub/infrastructure/providers/pixiv/content_processor.py
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple

from loguru import logger

from ....domain.interfaces import IPixivImageDownloader
from ....models.domain import NovelMetadata
from ....models.pixiv import NovelApiResponse
from ....models.workspace import Workspace
from ....shared.constants import IMAGES_DIR_NAME
from ...strategies.interfaces import IContentParser, IMetadataMapper
from ...strategies.update_checkers import IUpdateCheckStrategy


class PixivContentProcessor:
    """
    APIから取得したデータを処理し、ワークスペースを構築する責務を持つクラス。
    """

    def __init__(
        self,
        parser: IContentParser,
        mapper: IMetadataMapper,
        downloader: IPixivImageDownloader,
        update_checker: IUpdateCheckStrategy,
    ):
        self.parser = parser
        self.mapper = mapper
        self.downloader = downloader
        self.update_checker = update_checker

    def check_for_updates(
        self, workspace: Workspace, raw_webview_novel_data: Dict
    ) -> Tuple[bool, str]:
        """コンテンツの更新が必要かチェックし、必要ならワークスペースをクリーンアップします。"""
        update_required, new_hash = self.update_checker.is_update_required(
            workspace, raw_webview_novel_data
        )
        if update_required:
            logger.info("コンテンツの更新を検出（または新規ダウンロードです）。")
            if workspace.source_path.exists():
                shutil.rmtree(workspace.source_path)
            workspace.source_path.mkdir(parents=True, exist_ok=True)
        return update_required, new_hash

    def process_and_populate_workspace(
        self,
        workspace: Workspace,
        raw_webview_novel_data: Dict,
        raw_novel_detail_data: Dict,
    ) -> NovelMetadata:
        """
        コンテンツをパースし、画像をダウンロードし、XHTMLを保存し、
        最終的なメタデータを生成して返します。
        """
        # 1. アセットのダウンロード
        cover_path = self._download_assets(workspace, raw_novel_detail_data)

        # 2. コンテンツの解析と保存
        novel_data, image_paths, parsed_text = self._process_and_save_content(
            workspace, raw_webview_novel_data
        )

        # 3. メタデータのマッピング
        parsed_description = self.parser.parse(
            raw_novel_detail_data.get("novel", {}).get("caption", ""), image_paths
        )
        metadata = self.mapper.map_to_metadata(
            workspace=workspace,
            cover_path=cover_path,
            novel_data=novel_data,
            detail_data=raw_novel_detail_data,
            parsed_text=parsed_text,
            parsed_description=parsed_description,
        )

        return metadata

    def _download_assets(
        self, workspace: Workspace, raw_novel_detail_data: Dict
    ) -> Optional[Path]:
        """ダウンローダーを使い、アセットをダウンロードします。"""
        image_dir = workspace.assets_path / IMAGES_DIR_NAME
        cover_path = self.downloader.download_cover(
            raw_novel_detail_data.get("novel", {}), image_dir=image_dir
        )
        return cover_path

    def _process_and_save_content(
        self,
        workspace: Workspace,
        raw_webview_novel_data: Dict,
    ) -> Tuple[NovelApiResponse, Dict[str, Path], str]:
        """コンテンツをパースし、画像をダウンロードし、XHTMLを保存します。"""
        novel_data = NovelApiResponse.model_validate(raw_webview_novel_data)

        image_dir = workspace.assets_path / IMAGES_DIR_NAME
        image_paths = self.downloader.download_embedded_images(
            novel_data, image_dir=image_dir
        )

        parsed_text = self.parser.parse(novel_data.text, image_paths)

        pages = parsed_text.split("[newpage]")
        for i, page_content in enumerate(pages):
            filename = workspace.source_path / f"page-{i + 1}.xhtml"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page_content)
            except IOError as e:
                logger.bind(page=i + 1, error=str(e)).error(
                    "ページの保存に失敗しました。"
                )
        logger.bind(page_count=len(pages)).debug("ページの保存が完了しました。")

        return novel_data, image_paths, parsed_text
