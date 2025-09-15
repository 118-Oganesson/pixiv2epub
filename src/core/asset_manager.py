import logging
import re
from pathlib import Path
from typing import List, Optional, Set, Tuple

from ..data.models import ImageAsset, NovelMetadata, PageInfo
from ..utils.path_manager import PathManager

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
    """ファイル名の拡張子からMIMEタイプを取得します。"""
    ext = filename.lower().split(".")[-1]
    return MEDIA_TYPES.get(ext, "application/octet-stream")


class AssetManager:
    """EPUBに含めるアセットの収集・整理を担当するクラス。"""

    def __init__(
        self, paths: PathManager, metadata: NovelMetadata, css_file_rel_path: str
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.paths = paths
        self.metadata = metadata
        self.css_file_rel_path = css_file_rel_path

    def gather_assets(
        self,
    ) -> Tuple[List[ImageAsset], List[PageInfo], Optional[ImageAsset]]:
        """アセットを収集・整理し、最終的にEPUBに含めるべきものを返す。"""
        all_images = self._collect_image_files()

        cover_image_asset = self._find_cover_image(all_images)

        referenced_filenames = self._extract_referenced_image_filenames(
            cover_image_asset
        )
        self.logger.debug(
            f"本文・CSSで参照されている画像: {sorted(list(referenced_filenames))}"
        )

        final_images = [
            img for img in all_images if img.filename in referenced_filenames
        ]
        # 参照がなくてもカバー画像だけは必ず含める
        if cover_image_asset and cover_image_asset.filename not in referenced_filenames:
            final_images.append(cover_image_asset)

        return final_images, self.metadata.pages, cover_image_asset

    def _collect_image_files(self) -> List[ImageAsset]:
        """`images` ディレクトリから画像ファイル情報を収集します。"""
        image_assets = []
        if not self.paths.image_dir.is_dir():
            return image_assets

        image_paths = sorted([p for p in self.paths.image_dir.iterdir() if p.is_file()])
        for i, path in enumerate(image_paths, 1):
            image_assets.append(
                ImageAsset(
                    id=f"img_{i}",
                    href=f"images/{path.name}",
                    path=path,
                    media_type=get_media_type_from_filename(path.name),
                    properties="",
                    filename=path.name,
                )
            )
        return image_assets

    def _find_cover_image(self, image_assets: List[ImageAsset]) -> Optional[ImageAsset]:
        """メタデータで指定されたカバー画像を特定します。"""
        if not self.metadata.cover_path:
            return None
        cover_filename = Path(self.metadata.cover_path).name
        for i, asset in enumerate(image_assets):
            if asset.filename == cover_filename:
                image_assets[i] = asset._replace(properties="cover-image")
                return image_assets[i]
        self.logger.warning(
            f"指定されたカバー画像 '{cover_filename}' が見つかりませんでした。"
        )
        return None

    def _extract_referenced_image_filenames(
        self, cover_asset: Optional[ImageAsset]
    ) -> Set[str]:
        """本文やCSSから参照されている画像ファイル名のセットを抽出します。"""
        filenames = set()

        def add_filename_from_path(path: str):
            p = path.strip()
            if not p or p.startswith(("http", "/", "data:")):
                return
            filenames.add(Path(re.sub(r"^\.?/+", "", p)).name)

        for page_info in self.metadata.pages:
            page_file = self.paths.novel_dir / page_info.body_path.lstrip("./")
            if not page_file.is_file():
                continue
            try:
                content = page_file.read_text(encoding="utf-8")
                for match in re.finditer(r'src=(["\'])(.*?)\1', content, re.IGNORECASE):
                    add_filename_from_path(match.group(2))
            except Exception as e:
                self.logger.warning(
                    f"ページファイル '{page_file.name}' の解析に失敗: {e}"
                )

        css_path = self.paths.novel_dir / self.css_file_rel_path
        if css_path.is_file():
            try:
                css_text = css_path.read_text(encoding="utf-8")
                for match in re.finditer(
                    r'url\((["\']?)(.*?)\1\)', css_text, re.IGNORECASE
                ):
                    add_filename_from_path(match.group(2))
            except Exception as e:
                self.logger.warning(f"CSSファイルの解析に失敗: {e}")

        if cover_asset:
            filenames.add(cover_asset.filename)

        return filenames
