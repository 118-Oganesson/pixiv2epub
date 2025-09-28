# src/pixiv2epub/builders/epub/generator.py

import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from ...models.local import (
    EpubComponents,
    ImageAsset,
    NovelMetadata,
    PageAsset,
    PageInfo,
)
from ...models.workspace import Workspace

# 決定論的なブックIDを生成するための固定の名前空間UUID
PIXIV_NAMESPACE_UUID = uuid.UUID("c22d7879-055f-4203-be9b-7f11e9f23a85")


class EpubGenerator:
    """EPUBの構成要素を生成するクラス。"""

    def __init__(
        self, metadata: NovelMetadata, workspace: Workspace, template_dir: Path
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.metadata = metadata
        self.workspace = workspace
        self.template_env = Environment(
            loader=FileSystemLoader(str(template_dir)), autoescape=True
        )

    def generate_components(
        self,
        image_assets: List[ImageAsset],
        page_infos: List[PageInfo],
        cover_asset: Optional[ImageAsset],
    ) -> EpubComponents:
        """EPUBの全構成要素を生成し、EpubComponentsオブジェクトとして返します。"""
        css_asset = self._generate_css()
        css_rel_path = css_asset.href if css_asset else None

        final_pages = self._generate_main_pages(page_infos, css_rel_path)
        info_page = self._generate_info_page(css_rel_path)
        cover_page = self._generate_cover_page(cover_asset)
        content_opf = self._generate_opf(
            final_pages, image_assets, info_page, cover_page, cover_asset, css_asset
        )
        nav_xhtml = self._generate_nav(final_pages, info_page, cover_page is not None)

        return EpubComponents(
            final_pages=final_pages,
            final_images=image_assets,
            info_page=info_page,
            cover_page=cover_page,
            css_asset=css_asset,
            content_opf=content_opf,
            nav_xhtml=nav_xhtml,
        )

    def _generate_css(self) -> Optional[PageAsset]:
        """style.css.j2 テンプレートをレンダリングします。"""
        try:
            content_bytes = self._render_template("epub/pixiv/style.css.j2", {})
            return PageAsset(
                id="css_style",
                href="css/style.css",
                content=content_bytes,
                title="stylesheet",
            )
        except Exception as e:
            self.logger.warning(f"CSSテンプレートのレンダリングに失敗: {e}")
            return None

    def _render_template(self, template_name: str, context: Dict) -> bytes:
        template = self.template_env.get_template(template_name)
        rendered_str = template.render(context)
        return rendered_str.encode("utf-8")

    def _generate_main_pages(
        self, page_infos: List[PageInfo], css_path: Optional[str]
    ) -> List[PageAsset]:
        """本文の各ページをXHTMLに変換します。"""
        pages = []
        for i, page_info in enumerate(page_infos, 1):
            raw_content_path = self.workspace.source_path / page_info.body.lstrip("./")
            try:
                content = raw_content_path.read_text(encoding="utf-8")

                # --- ▼▼▼ 修正点 ▼▼▼ ---
                # 中間ファイル用の画像パスを、最終的なEPUB内のパスに置換する
                content = content.replace("../assets/images/", "../images/")
                # --- ▲▲▲ 修正点 ▲▲▲ ---

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
            except Exception as e:
                self.logger.error(f"ページの処理中にエラー: {page_info.title}, {e}")
        return pages

    def _generate_info_page(self, css_path: Optional[str]) -> PageAsset:
        """作品情報ページを生成します。"""
        # 日付フォーマット処理を追加
        formatted_date = self.metadata.date
        try:
            if self.metadata.date:
                dt_object = datetime.fromisoformat(self.metadata.date)
                formatted_date = dt_object.strftime("%Y年%m月%d日 %H:%M")
        except (ValueError, TypeError):
            pass  # フォーマットできない場合は元の文字列を使用

        context = {
            "title": self.metadata.title,
            "css_path": css_path,
            "novel": {
                "title": self.metadata.title,
                "author": self.metadata.authors.name,
                "series_title": self.metadata.series.title
                if self.metadata.series
                else None,
                "series_order": self.metadata.series.order
                if self.metadata.series
                else None,
                "description": self.metadata.description,
                "tags": self.metadata.tags,
                "source_url": self.metadata.original_source,
                "meta_info": f"公開日: {formatted_date}, 文字数: {self.metadata.text_length or 'N/A'}",
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
        css_asset: Optional[PageAsset],  # 引数を変更
    ) -> bytes:
        """content.opf ファイルの内容を生成します。"""
        manifest_items, spine_itemrefs = [], []
        manifest_items.append(
            {
                "id": "nav",
                "href": "nav.xhtml",
                "media_type": "application/xhtml+xml",
                "properties": "nav",
            }
        )
        if css_asset:
            manifest_items.append(
                {
                    "id": css_asset.id,
                    "href": css_asset.href,
                    "media_type": "text/css",
                }
            )
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
        for image in images:
            manifest_items.append(image._asdict())

        metadata_as_dict = asdict(self.metadata)

        novel_id = self.metadata.identifier.get("novel_id")
        deterministic_uuid = uuid.uuid5(PIXIV_NAMESPACE_UUID, str(novel_id))
        metadata_as_dict["identifier"]["uuid"] = f"urn:uuid:{deterministic_uuid}"

        context = {
            "metadata": metadata_as_dict,
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
