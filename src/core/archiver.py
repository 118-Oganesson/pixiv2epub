import logging
import zipfile
from pathlib import Path
from typing import Optional

from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

from ..data.models import EpubComponents
from ..utils.compressor import ImageCompressor


class Archiver:
    """EPUBコンポーネントをZIPファイルに圧縮・梱包するクラス。

    EPUBは実質的に特定の規約に従ったZIPファイルであるため、
    このクラスが最終的なファイル生成を担当します。
    """

    def __init__(self, config: dict):
        """Archiverのインスタンスを初期化します。

        Args:
            config (dict): アプリケーション全体の設定情報。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config

    def archive(self, components: "EpubComponents", output_path: Path):
        """準備されたコンポーネントをZIPファイルに書き込み、EPUBを生成します。

        Args:
            components (EpubComponents): EPUBを構成する全てのコンポーネントを持つデータクラス。
            output_path (Path): 生成されるEPUBファイルの出力先パス。
        """
        compress_images = self.config.get("compression", {}).get("enabled", False)
        img_compressor = ImageCompressor(self.config) if compress_images else None

        # EPUBコンテナのルートを定義するcontainer.xmlファイル
        container_xml = b'<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'

        with zipfile.ZipFile(output_path, "w") as zf:
            # EPUB仕様: mimetypeファイルは無圧縮で、アーカイブの先頭に配置する必要がある
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

            if components.css_file_path:
                zf.write(
                    components.css_file_path, f"OEBPS/{components.css_file_path.name}"
                )

            # 画像の圧縮と書き込みには時間がかかる場合があるため、進捗バーを表示する
            with Progress(
                TextColumn("[bold blue]Compressing images..."),
                BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task("compress", total=len(components.final_images))
                for image in components.final_images:
                    self._write_image(zf, image, img_compressor)
                    progress.update(task, advance=1)

        self.logger.debug(f"EPUB を生成しました: {output_path}")

    def _write_image(
        self, zf: zipfile.ZipFile, image, compressor: Optional[ImageCompressor]
    ):
        """単一の画像ファイルを読み込み、必要に応じて圧縮してZIPファイルに書き込みます。

        Args:
            zf (zipfile.ZipFile): 書き込み先のZIPファイルオブジェクト。
            image: 書き込む画像の情報を持つImageAsset。
            compressor (Optional[ImageCompressor]): 画像圧縮を行うコンプレッサー。
        """
        try:
            file_bytes = image.path.read_bytes()
            if compressor:
                result = compressor.compress_file(
                    input_path=image.path, return_bytes=True, write_output=False
                )
                if result.success and not result.skipped and result.output_bytes:
                    file_bytes = result.output_bytes
            zf.writestr(f"OEBPS/{image.href}", file_bytes)
        except IOError as e:
            self.logger.error(f"画像ファイルの読み込み/書き込み失敗: {image.path}, {e}")
