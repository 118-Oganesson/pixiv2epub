#
# -----------------------------------------------------------------------------
# src/pixiv2epub/builders/epub/asset_manager.py
#
# EPUBに含めるアセット（画像ファイルなど）の収集と整理を担当します。
#
# 本文やCSSから実際に参照されている画像ファイルのみを抽出し、
# 不要なファイルがEPUBに含まれないようにする責務を持ちます。
# -----------------------------------------------------------------------------
import logging
import re
from pathlib import Path
from typing import List, Optional, Set, Tuple

from ...data_models import ImageAsset, NovelMetadata, PageInfo
from ...utils.path_manager import PathManager
from ...constants import IMAGES_DIR_NAME

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

    def __init__(self, paths: PathManager, metadata: NovelMetadata, css_file_path: Optional[Path]):
        """
        AssetManagerのインスタンスを初期化します。

        Args:
            paths (PathManager): パス管理用のユーティリティインスタンス。
            metadata (NovelMetadata): 小説のメタデータ。
            css_file_path (Optional[Path]): CSSファイルの絶対パス。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.paths = paths
        self.metadata = metadata
        self.css_file_path = css_file_path

    def gather_assets(
        self,
    ) -> Tuple[List[ImageAsset], List[PageInfo], Optional[ImageAsset]]:
        """
        アセットを収集、整理し、EPUBに含めるべき最終的なリストを返します。

        Returns:
            Tuple[List[ImageAsset], List[PageInfo], Optional[ImageAsset]]:
                - 最終的にEPUBに含める画像アセットのリスト。
                - ページ情報のリスト（メタデータから取得）。
                - カバー画像として特定されたImageAsset（存在しない場合はNone）。
        """
        all_images = self._collect_image_files()
        cover_image_asset = self._find_cover_image(all_images)

        referenced_filenames = self._extract_referenced_image_filenames()
        self.logger.debug(
            f"本文・CSSで参照されている画像: {sorted(list(referenced_filenames))}"
        )

        final_images = [
            img for img in all_images if img.filename in referenced_filenames
        ]
        
        # カバー画像は本文中で参照されていなくても必ずEPUBに含める
        if cover_image_asset and cover_image_asset.filename not in referenced_filenames:
            final_images.append(cover_image_asset)

        return final_images, self.metadata.pages, cover_image_asset

    def _collect_image_files(self) -> List[ImageAsset]:
        """`images`ディレクトリから画像ファイルを収集し、ImageAssetのリストを生成します。"""
        image_assets = []
        if not self.paths.image_dir.is_dir():
            return image_assets

        image_paths = sorted([p for p in self.paths.image_dir.iterdir() if p.is_file()])
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
        self.logger.warning(
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
            # パスの '../' や './' を正規化してファイル名だけを抽出
            filenames.add(Path(p).name)

        # 全てのページファイルを解析
        for page_info in self.metadata.pages:
            page_file = self.paths.novel_dir / page_info.body_path.lstrip("./")
            if not page_file.is_file():
                continue
            try:
                content = page_file.read_text(encoding="utf-8")
                # src="..." or src='...' 形式の画像参照を検索
                for match in re.finditer(r'src=(["\'])(.*?)\1', content, re.IGNORECASE):
                    add_filename_from_path(match.group(2))
            except Exception as e:
                self.logger.warning(
                    f"ページファイル '{page_file.name}' の解析に失敗: {e}"
                )

        # CSSファイルを解析
        if self.css_file_path and self.css_file_path.is_file():
            try:
                css_text = self.css_file_path.read_text(encoding="utf-8")
                # url(...) 形式の画像参照を検索
                for match in re.finditer(
                    r'url\((.*?)\)', css_text, re.IGNORECASE
                ):
                    add_filename_from_path(match.group(1))
            except Exception as e:
                self.logger.warning(f"CSSファイルの解析に失敗: {e}")

        return filenames
