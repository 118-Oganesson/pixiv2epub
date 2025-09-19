#
# -----------------------------------------------------------------------------
# src/pixiv2epub/builders/epub/generator.py
#
# EPUBを構成する各要素（XHTML, OPF, NCXなど）を生成する責務を持つクラス。
#
# Jinja2テンプレートエンジンを利用して、メタデータとアセット情報から
# EPUBの仕様に準拠したファイルを動的に生成します。
# -----------------------------------------------------------------------------
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from ...data_models import (
    EpubComponents,
    ImageAsset,
    NovelMetadata,
    PageAsset,
    PageInfo,
)
from ...utils.path_manager import PathManager


class EpubGenerator:
    """EPUBの構成要素を生成するクラス。"""

    def __init__(
        self,
        config: Dict[str, Any],
        metadata: NovelMetadata,
        paths: PathManager,
        template_dir: Path,
    ):
        """
        EpubGeneratorを初期化します。

        Args:
            config (dict): アプリケーション全体の設定情報。
            metadata (NovelMetadata): 小説のメタデータ。
            paths (PathManager): パス管理ユーティリティ。
            template_dir (Path): Jinja2テンプレートが格納されているディレクトリのパス。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.metadata = metadata
        self.paths = paths
        self.template_env = Environment(
            loader=FileSystemLoader(str(template_dir)), autoescape=True
        )

    def generate_components(
        self,
        image_assets: List[ImageAsset],
        page_infos: List[PageInfo],
        cover_asset: Optional[ImageAsset],
        css_path: Optional[Path],
    ) -> EpubComponents:
        """
        EPUBの全構成要素を生成し、EpubComponentsオブジェクトとして返します。

        Args:
            image_assets (List[ImageAsset]): EPUBに含める画像アセットのリスト。
            page_infos (List[PageInfo]): 各ページのメタ情報リスト。
            cover_asset (Optional[ImageAsset]): カバー画像のアセット。
            css_path (Optional[Path]): スタイルシートのパス。

        Returns:
            EpubComponents: 生成された全コンポーネントを格納したデータクラス。
        """
        css_rel_path = (
            f"css/{css_path.name}" if css_path and css_path.is_file() else None
        )

        # 1. 各本文ページ(XHTML)を生成
        final_pages = self._generate_main_pages(page_infos, css_rel_path)

        # 2. 作品情報ページとカバーページを生成
        info_page = self._generate_info_page(css_rel_path)
        cover_page = self._generate_cover_page(cover_asset)

        # 3. content.opf (パッケージドキュメント) を生成
        content_opf = self._generate_opf(
            final_pages, image_assets, info_page, cover_page, cover_asset, css_path
        )

        # 4. nav.xhtml (目次) を生成
        nav_xhtml = self._generate_nav(final_pages, info_page, cover_page is not None)

        return EpubComponents(
            final_pages=final_pages,
            final_images=image_assets,
            info_page=info_page,
            cover_page=cover_page,
            css_file_path=css_path,
            content_opf=content_opf,
            nav_xhtml=nav_xhtml,
        )

    def _render_template(self, template_name: str, context: Dict) -> bytes:
        """Jinja2テンプレートをレンダリングしてバイト列として返します。"""
        template = self.template_env.get_template(template_name)
        rendered_str = template.render(context)
        return rendered_str.encode("utf-8")

    def _generate_main_pages(
        self, page_infos: List[PageInfo], css_path: Optional[str]
    ) -> List[PageAsset]:
        """本文の各ページをXHTMLに変換します。"""
        pages = []
        for i, page_info in enumerate(page_infos, 1):
            raw_content_path = self.paths.novel_dir / page_info.body_path.lstrip("./")
            try:
                content = raw_content_path.read_text(encoding="utf-8")
                context = {
                    "title": page_info.title,
                    "content": content,
                    "css_path": css_path,
                }
                page_content_bytes = self._render_template(
                    "epub/pixiv/page_wrapper.xhtml.j2", context
                )
                pages.append(
                    PageAsset(
                        id=f"page_{i}",
                        href=f"text/page-{i}.xhtml",
                        content=page_content_bytes,
                        title=page_info.title,
                    )
                )
            except FileNotFoundError:
                self.logger.warning(
                    f"ページファイルが見つかりません: {raw_content_path}"
                )
            except Exception as e:
                self.logger.error(
                    f"ページの処理中にエラーが発生しました: {page_info.title}, {e}"
                )
        return pages

    def _generate_info_page(self, css_path: Optional[str]) -> PageAsset:
        """作品情報ページを生成します。"""
        context = {
            "title": self.metadata.title,
            "css_path": css_path,
            "novel": {
                "title": self.metadata.title,
                "author": self.metadata.authors.name,
                "series_title": self.metadata.series.title
                if self.metadata.series
                else None,
                "description": self.metadata.description,
                "tags": self.metadata.tags,
                "source_url": self.metadata.original_source,
                "meta_info": f"公開日: {self.metadata.date}, 文字数: {self.metadata.text_length or 'N/A'}",
            },
        }
        content_bytes = self._render_template("epub/pixiv/info_page.xhtml.j2", context)
        return PageAsset(
            id="info_page",
            href="text/info.xhtml",
            content=content_bytes,
            title="作品情報",
        )

    def _generate_cover_page(
        self, cover_asset: Optional[ImageAsset]
    ) -> Optional[PageAsset]:
        """カバーページを生成します。"""
        if not cover_asset:
            return None
        context = {"cover_image_href": f"../{cover_asset.href}"}
        content_bytes = self._render_template("epub/pixiv/cover_page.xhtml.j2", context)
        return PageAsset(
            id="cover_page",
            href="text/cover.xhtml",
            content=content_bytes,
            title="表紙",
        )

    def _generate_opf(
        self,
        pages: List[PageAsset],
        images: List[ImageAsset],
        info_page: PageAsset,
        cover_page: Optional[PageAsset],
        cover_asset: Optional[ImageAsset],
        css_path: Optional[Path],
    ) -> bytes:
        """content.opf ファイルの内容を生成します。"""
        manifest_items = []
        spine_itemrefs = []

        # Nav
        manifest_items.append(
            {
                "id": "nav",
                "href": "nav.xhtml",
                "media_type": "application/xhtml+xml",
                "properties": "nav",
            }
        )

        # CSS
        if css_path and css_path.is_file():
            manifest_items.append(
                {
                    "id": "css_style",
                    "href": f"css/{css_path.name}",
                    "media_type": "text/css",
                }
            )

        # Pages (Info, Cover, Main)
        if cover_page:
            manifest_items.append(
                {
                    "id": cover_page.id,
                    "href": cover_page.href,
                    "media_type": "application/xhtml+xml",
                }
            )
            spine_itemrefs.append({"idref": cover_page.id, "linear": False})

        manifest_items.append(
            {
                "id": info_page.id,
                "href": info_page.href,
                "media_type": "application/xhtml+xml",
            }
        )
        spine_itemrefs.append({"idref": info_page.id, "linear": True})

        for page in pages:
            manifest_items.append(
                {
                    "id": page.id,
                    "href": page.href,
                    "media_type": "application/xhtml+xml",
                }
            )
            spine_itemrefs.append({"idref": page.id, "linear": True})

        # Images
        for image in images:
            manifest_items.append(image._asdict())

        context = {
            "metadata": self.metadata,
            "formatted_date": self.metadata.date,
            "modified_time": datetime.now(timezone.utc).isoformat(),
            "manifest_items": manifest_items,
            "spine_itemrefs": spine_itemrefs,
            "cover_image_id": cover_asset.id if cover_asset else None,
        }
        return self._render_template("epub/pixiv/content.opf.j2", context)

    def _generate_nav(
        self, pages: List[PageAsset], info_page: PageAsset, has_cover: bool
    ) -> bytes:
        """nav.xhtml (目次) ファイルの内容を生成します。"""
        nav_pages = [{"href": p.href, "title": p.title} for p in pages]
        context = {
            "pages": nav_pages,
            "has_info_page": True,
            "info_page_title": info_page.title,
            "has_cover": has_cover,
        }
        return self._render_template("epub/pixiv/nav.xhtml.j2", context)
