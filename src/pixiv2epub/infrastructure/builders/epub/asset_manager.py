# FILE: src/pixiv2epub/infrastructure/builders/epub/asset_manager.py
import re
from pathlib import Path
from typing import List, Optional, Set, Tuple

from loguru import logger

from ....shared.constants import IMAGES_DIR_NAME
from ....models.local import ImageAsset, NovelMetadata, PageInfo
from ....models.workspace import Workspace

MEDIA_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "svg": "image/svg+xml",
    "webp": "image/webp",
    "xhtml": "application/xhtml+xml",
    "css": "text/css",
}


def get_media_type_from_filename(filename: str) -> str:
    """ファイル名の拡張子からMIMEタイプを返します。"""
    ext = filename.lower().split(".")[-1]
    return MEDIA_TYPES.get(ext, "application/octet-stream")


class AssetManager:
    """EPUBアセットの収集・整理を担当するクラス。"""

    def __init__(
        self,
        workspace: Workspace,
        metadata: NovelMetadata,
    ):
        self.workspace = workspace
        self.metadata = metadata
        self.source_dir = workspace.source_path
        self.image_dir = workspace.assets_path / IMAGES_DIR_NAME

    def gather_assets(
        self,
    ) -> Tuple[List[ImageAsset], List[PageInfo], Optional[ImageAsset]]:
        """アセットを収集、整理し、EPUBに含めるべき最終的なリストを返します。"""
        all_images = self._collect_image_files()
        cover_image_asset = self._find_cover_image(all_images)
        referenced_filenames = self._extract_referenced_image_filenames()
        final_images = [
            img for img in all_images if img.filename in referenced_filenames
        ]

        if cover_image_asset and cover_image_asset.filename not in referenced_filenames:
            final_images.append(cover_image_asset)

        return final_images, self.metadata.pages, cover_image_asset

    def _collect_image_files(self) -> List[ImageAsset]:
        """`assets/images`ディレクトリから画像ファイルを収集します。"""
        image_assets = []
        if not self.image_dir.is_dir():
            return image_assets
        image_paths = sorted([p for p in self.image_dir.iterdir() if p.is_file()])
        for i, path in enumerate(image_paths, 1):
            image_assets.append(
                ImageAsset(
                    id=f"img_{i}",
                    href=f"{IMAGES_DIR_NAME}/{path.name}",
                    path=path,
                    media_type=get_media_type_from_filename(path.name),
                    properties="",
                    filename=path.name,
                )
            )
        return image_assets

    def _find_cover_image(self, image_assets: List[ImageAsset]) -> Optional[ImageAsset]:
        """メタデータで指定されたカバー画像を特定し、`properties`属性を更新します。"""
        if not self.metadata.cover_path:
            return None
        cover_filename = Path(self.metadata.cover_path).name
        for i, asset in enumerate(image_assets):
            if asset.filename == cover_filename:
                image_assets[i] = asset._replace(properties="cover-image")
                return image_assets[i]
        logger.warning(
            f"指定されたカバー画像 '{cover_filename}' が見つかりませんでした。"
        )
        return None

    def _extract_referenced_image_filenames(self) -> Set[str]:
        """本文(XHTML)やCSSファイル内から参照されている画像ファイル名を抽出します。"""
        filenames = set()

        def add_filename_from_path(path: str):
            p = path.strip().strip("'\"")
            if not p or p.startswith(("http", "data:")):
                return
            # パスからファイル名のみを抽出
            # 例: ../assets/images/foo.jpg -> foo.jpg
            filenames.add(Path(p).name)

        for page_info in self.metadata.pages:
            # page_info.body は "./page-1.xhtml" のような相対パス
            page_file = self.source_dir / page_info.body.lstrip("./")
            if not page_file.is_file():
                continue
            try:
                content = page_file.read_text(encoding="utf-8")
                for match in re.finditer(r'src=(["\'])(.*?)\1', content, re.IGNORECASE):
                    add_filename_from_path(match.group(2))
            except Exception as e:
                logger.warning(f"ページファイル '{page_file.name}' の解析に失敗: {e}")

        return filenames
