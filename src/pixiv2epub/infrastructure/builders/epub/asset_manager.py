# FILE: src/pixiv2epub/infrastructure/builders/epub/asset_manager.py
import re
from pathlib import Path

from loguru import logger

from ....models.domain import ImageAsset, UCMResource, UnifiedContentManifest
from ....models.workspace import Workspace
from ....shared.constants import IMAGES_DIR_NAME
from ....utils.common import get_media_type_from_filename


class AssetManager:
    """EPUBアセットの収集・整理を担当するクラス。"""

    def __init__(
        self,
        workspace: Workspace,
        manifest: UnifiedContentManifest,
    ):
        self.workspace = workspace
        self.manifest = manifest
        self.source_dir = workspace.source_path
        self.image_dir = workspace.assets_path / IMAGES_DIR_NAME

    def gather_assets(
        self,
    ) -> tuple[list[ImageAsset], ImageAsset | None]:
        """アセットを収集、整理し、EPUBに含めるべき最終的なリストを返します。"""
        all_images = self._collect_image_files()

        # UCMの resources から cover_key を見つける
        cover_key = self.manifest.core.image
        cover_resource = self.manifest.resources.get(cover_key) if cover_key else None

        cover_image_asset = self._find_cover_image(all_images, cover_resource)
        referenced_filenames = self._extract_referenced_image_filenames()
        final_images = [
            img for img in all_images if img.filename in referenced_filenames
        ]

        if cover_image_asset and cover_image_asset.filename not in referenced_filenames:
            final_images.append(cover_image_asset)

        return final_images, cover_image_asset

    def _collect_image_files(self) -> list[ImageAsset]:
        """`assets/images`ディレクトリから画像ファイルを収集します。"""
        image_assets = []
        if not self.image_dir.is_dir():
            return image_assets
        image_paths = sorted([p for p in self.image_dir.iterdir() if p.is_file()])
        for i, path in enumerate(image_paths, 1):
            image_assets.append(
                ImageAsset(
                    id=f'img_{i}',
                    href=f'{IMAGES_DIR_NAME}/{path.name}',
                    path=path,
                    media_type=get_media_type_from_filename(path.name),
                    properties='',
                    filename=path.name,
                )
            )
        return image_assets

    def _find_cover_image(
        self, image_assets: list[ImageAsset], cover_resource: UCMResource | None
    ) -> ImageAsset | None:
        """UCMで指定されたカバー画像を特定し、`properties`属性を更新します。"""
        if not cover_resource:
            return None

        # UCMのパス (例: ../assets/images/cover.jpg) からファイル名のみを抽出
        cover_filename = Path(cover_resource.path).name

        for i, asset in enumerate(image_assets):
            if asset.filename == cover_filename:
                updated_asset = asset.model_copy(update={'properties': 'cover-image'})
                image_assets[i] = updated_asset
                return image_assets[i]

        logger.warning(
            "指定されたカバー画像 '{}' が見つかりませんでした。", cover_filename
        )
        return None

    def _extract_referenced_image_filenames(self) -> set[str]:
        """本文(XHTML)やCSSファイル内から参照されている画像ファイル名を抽出します。"""
        filenames = set()

        def add_filename_from_path(path: str) -> None:
            p = path.strip().strip('\'"')
            if not p or p.startswith(('http', 'data:')):
                return
            # パスからファイル名のみを抽出
            # 例: ../assets/images/foo.jpg -> foo.jpg
            filenames.add(Path(p).name)

        # manifest.contentStructure からページファイルを反復処理
        for page_block in self.manifest.contentStructure:
            resource_key = page_block.source
            page_resource = self.manifest.resources.get(resource_key)
            if not page_resource or page_resource.role != 'content':
                continue

            # UCM のリソースパス (例: "./page-1.xhtml") を使用
            page_file = self.source_dir / page_resource.path.lstrip('./')

            if not page_file.is_file():
                continue
            try:
                content = page_file.read_text(encoding='utf-8')
                for match in re.finditer(r'src=(["\'])(.*?)\1', content, re.IGNORECASE):
                    add_filename_from_path(match.group(2))
            except Exception as e:
                logger.warning(
                    "ページファイル '{}' の解析に失敗: {}", page_file.name, e
                )

        return filenames
