# FILE: src/pixiv2epub/infrastructure/builders/epub/package_assembler.py
import zipfile
from pathlib import Path

from loguru import logger

from ....models.domain import EpubComponents, ImageAsset
from ....shared.settings import Settings
from ....utils.image_optimizer import ImageCompressor
from .constants import (
    CONTAINER_XML_PATH,
    MIMETYPE_FILE_NAME,
    NAV_XHTML_PATH,
    OEBPS_DIR,
    ROOT_FILE_PATH,
)

CONTAINER_XML_RESOURCE_PATH = Path(__file__).parent / 'assets' / 'container.xml'
MIMETYPE_RESOURCE_PATH = Path(__file__).parent / 'assets' / MIMETYPE_FILE_NAME


class EpubPackageAssembler:
    """EPUBコンポーネントをZIPファイルに圧縮・梱包するクラス。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.img_optimizer = (
            ImageCompressor(self.settings)
            if self.settings.compression.enabled
            else None
        )

    def archive(self, components: 'EpubComponents', output_path: Path) -> None:
        """準備されたコンポーネントをZIPファイルに書き込み、EPUBを生成します。"""
        try:
            mimetype_content = MIMETYPE_RESOURCE_PATH.read_bytes()
            container_content = CONTAINER_XML_RESOURCE_PATH.read_bytes()
        except OSError as e:
            logger.error(
                f'コンテナリソースの読み込みに失敗: {CONTAINER_XML_RESOURCE_PATH}. {e}'
            )
            raise
        with zipfile.ZipFile(output_path, 'w') as zip_file:
            zip_file.writestr(
                MIMETYPE_FILE_NAME, mimetype_content, compress_type=zipfile.ZIP_STORED
            )
            zip_file.writestr(CONTAINER_XML_PATH, container_content)
            zip_file.writestr(ROOT_FILE_PATH, components.content_opf)
            zip_file.writestr(NAV_XHTML_PATH, components.nav_xhtml)

            oebps_path = Path(OEBPS_DIR)

            zip_file.writestr(
                (oebps_path / components.info_page.href).as_posix(),
                components.info_page.content,
            )
            if components.cover_page:
                zip_file.writestr(
                    (oebps_path / components.cover_page.href).as_posix(),
                    components.cover_page.content,
                )
            for page in components.final_pages:
                zip_file.writestr((oebps_path / page.href).as_posix(), page.content)
            if components.css_asset:
                zip_file.writestr(
                    (oebps_path / components.css_asset.href).as_posix(),
                    components.css_asset.content,
                )

            if not components.final_images:
                logger.debug('画像ファイルはありません。')
                return

            logger.info(f'{len(components.final_images)}件の画像を処理します。')
            for image in components.final_images:
                self._write_image(zip_file, image, oebps_path)

        logger.debug(f'EPUB を生成しました: {output_path}')

    def _write_image(
        self, zip_file: zipfile.ZipFile, image: ImageAsset, prefix_path: Path
    ) -> None:
        """単一の画像ファイルを読み込み、必要に応じて圧縮してZIPファイルに書き込みます。"""
        try:
            file_bytes = image.path.read_bytes()
            if self.img_optimizer:
                result = self.img_optimizer.compress_file(
                    input_path=image.path, return_bytes=True, write_output=False
                )
                if result.success and not result.skipped and result.output_bytes:
                    file_bytes = result.output_bytes

            zip_file.writestr((prefix_path / image.href).as_posix(), file_bytes)
        except OSError as e:
            logger.error(f'画像ファイルの読み込み/書き込み失敗: {image.path}, {e}')
