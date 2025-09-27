# src/pixiv2epub/builders/epub/archiver.py

import logging
import zipfile
from pathlib import Path

from ...core.settings import Settings
from ...models.local import EpubComponents, ImageAsset
from ...utils.image_optimizer import ImageCompressor


class Archiver:
    """EPUBコンポーネントをZIPファイルに圧縮・梱包するクラス。"""

    def __init__(self, settings: Settings):
        """
        Args:
            settings (Settings): アプリケーション全体の設定情報。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.settings = settings
        self.img_optimizer = (
            ImageCompressor(self.settings)
            if self.settings.compression.enabled
            else None
        )

    def archive(self, components: "EpubComponents", output_path: Path):
        """準備されたコンポーネントをZIPファイルに書き込み、EPUBを生成します。"""
        container_xml = (
            b'<?xml version="1.0"?>'
            b'<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            b"<rootfiles>"
            b'<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
            b"</rootfiles>"
            b"</container>"
        )

        with zipfile.ZipFile(output_path, "w") as zf:
            zf.writestr(
                "mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED
            )
            zf.writestr("META-INF/container.xml", container_xml)
            zf.writestr("OEBPS/content.opf", components.content_opf)
            zf.writestr("OEBPS/nav.xhtml", components.nav_xhtml)
            zf.writestr(
                f"OEBPS/{components.info_page.href}", components.info_page.content
            )
            if components.cover_page:
                zf.writestr(
                    f"OEBPS/{components.cover_page.href}", components.cover_page.content
                )
            for page in components.final_pages:
                zf.writestr(f"OEBPS/{page.href}", page.content)
            if components.css_asset:
                zf.writestr(
                    f"OEBPS/{components.css_asset.href}", components.css_asset.content
                )
            if not components.final_images:
                self.logger.debug("画像ファイルはありません。")
                return

            self.logger.info(f"{len(components.final_images)}件の画像を処理します。")
            for image in components.final_images:
                self._write_image(zf, image)

        self.logger.debug(f"EPUB を生成しました: {output_path}")

    def _write_image(self, zf: zipfile.ZipFile, image: ImageAsset):
        """単一の画像ファイルを読み込み、必要に応じて圧縮してZIPファイルに書き込みます。"""
        try:
            file_bytes = image.path.read_bytes()
            if self.img_optimizer:
                result = self.img_optimizer.compress_file(
                    input_path=image.path, return_bytes=True, write_output=False
                )
                if result.success and not result.skipped and result.output_bytes:
                    file_bytes = result.output_bytes
            zf.writestr(f"OEBPS/{image.href}", file_bytes)
        except IOError as e:
            self.logger.error(f"画像ファイルの読み込み/書き込み失敗: {image.path}, {e}")
