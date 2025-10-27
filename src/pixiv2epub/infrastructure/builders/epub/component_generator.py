# FILE: src/pixiv2epub/infrastructure/builders/epub/component_generator.py
import re

from jinja2 import Environment
from loguru import logger

from ....models.domain import (
    EpubComponents,
    ImageAsset,
    PageAsset,
    UnifiedContentManifest,
)
from ....models.workspace import Workspace


class EpubComponentGenerator:
    """EPUBの構成要素を生成するクラス。"""

    def __init__(
        self,
        manifest: UnifiedContentManifest,
        workspace: Workspace,
        template_env: Environment,
    ):
        self.manifest = manifest
        self.workspace = workspace
        self.template_env = template_env

    def generate_components(
        self,
        image_assets: list[ImageAsset],
        cover_asset: ImageAsset | None,
    ) -> EpubComponents:
        """EPUBの全構成要素を生成し、EpubComponentsオブジェクトとして返します。"""
        css_asset = self._generate_css()
        css_rel_path = f'../{css_asset.href}' if css_asset else None

        plain_description = ''
        if self.manifest.core.description:
            plain_description = re.sub(r'<[^>]+>', '', self.manifest.core.description)
            plain_description = plain_description.replace('\n', ' ').strip()

        final_pages = self._generate_main_pages(css_rel_path)
        info_page = self._generate_info_page(css_rel_path, cover_asset)
        cover_page = self._generate_cover_page(cover_asset)

        content_opf = self._generate_opf(
            final_pages,
            image_assets,
            info_page,
            cover_page,
            cover_asset,
            css_asset,
            plain_description=plain_description,  #
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

    def _generate_css(self) -> PageAsset | None:
        """style.css.j2 テンプレートをレンダリングします。"""
        try:
            content_bytes = self._render_template('style.css.j2', {})
            return PageAsset(
                id='css_style',
                href='css/style.css',
                content=content_bytes,
                title='stylesheet',
            )
        except Exception as e:
            logger.warning(f'CSSテンプレートのレンダリングに失敗: {e}')
            return None

    def _render_template(self, template_name: str, context: dict) -> bytes:
        template = self.template_env.get_template(template_name)
        rendered_str = template.render(context)
        return rendered_str.encode('utf-8')

    def _generate_main_pages(self, css_path: str | None) -> list[PageAsset]:
        """本文の各ページをXHTMLに変換します。"""
        pages = []
        # UCM の contentStructure をループ
        for i, page_block in enumerate(self.manifest.contentStructure, 1):
            try:
                resource_key = page_block.source
                page_resource = self.manifest.resources.get(resource_key)
                if not page_resource or page_resource.role != 'content':
                    logger.error(f"ページリソース '{resource_key}' が見つかりません。")
                    continue

                # UCM のリソースパス (例: "./page-1.xhtml") を使用
                content = self.workspace.get_page_content(page_resource.path)
                # "../assets/images/foo.jpg" -> "../images/foo.jpg"
                content = re.sub(
                    r'src="\.\./assets/(images/.+?)"', r'src="../\1"', content
                )

                context = {
                    'title': page_block.title,
                    'content': content,
                    'css_path': css_path,
                }
                page_content_bytes = self._render_template(
                    'page_wrapper.xhtml.j2', context
                )
                pages.append(
                    PageAsset(
                        id=f'page_{i}',
                        href=f'text/page-{i}.xhtml',  # (リソースパスから導出する方が堅牢)
                        content=page_content_bytes,
                        title=page_block.title,
                    )
                )
            except Exception as e:
                logger.error(f'ページの処理中にエラー: {page_block.title}, {e}')
        return pages

    def _generate_info_page(
        self, css_path: str | None, cover_asset: ImageAsset | None
    ) -> PageAsset:
        """作品情報ページを生成します。"""
        core = self.manifest.core
        formatted_date = core.datePublished.strftime('%Y年%m月%d日 %H:%M')

        # providerDataから text_length を検索
        text_length = 'N/A'
        for item in self.manifest.providerData:
            if item.propertyID.endswith(':textLength'):
                text_length = item.value
                break

        context = {
            'manifest': self.manifest,
            'css_path': css_path,
            'formatted_date': formatted_date,
            'text_length': text_length,
            'cover_href': f'../{cover_asset.href}' if cover_asset else None,
        }
        content_bytes = self._render_template('info_page.xhtml.j2', context)
        return PageAsset(
            id='info_page',
            href='text/info.xhtml',
            content=content_bytes,
            title='作品情報',
        )

    def _generate_cover_page(self, cover_asset: ImageAsset | None) -> PageAsset | None:
        """カバーページを生成します。"""
        if not cover_asset:
            return None
        context = {'cover_image_href': f'../{cover_asset.href}'}
        content_bytes = self._render_template('cover_page.xhtml.j2', context)
        return PageAsset(
            id='cover_page',
            href='text/cover.xhtml',
            content=content_bytes,
            title='表紙',
        )

    def _generate_opf(
        self,
        pages: list[PageAsset],
        images: list[ImageAsset],
        info_page: PageAsset,
        cover_page: PageAsset | None,
        cover_asset: ImageAsset | None,
        css_asset: PageAsset | None,
        plain_description: str,
    ) -> bytes:
        """content.opf ファイルの内容を生成します。"""
        manifest_items, spine_itemrefs = [], []
        manifest_items.append(
            {
                'id': 'nav',
                'href': 'nav.xhtml',
                'media_type': 'application/xhtml+xml',
                'properties': 'nav',
            }
        )

        if css_asset:
            manifest_items.append(
                {
                    'id': css_asset.id,
                    'href': css_asset.href,
                    'media_type': 'text/css',
                }
            )

        if cover_page:
            manifest_items.append(
                {
                    'id': cover_page.id,
                    'href': cover_page.href,
                    'media_type': 'application/xhtml+xml',
                }
            )
            spine_itemrefs.append({'idref': cover_page.id, 'linear': False})

        manifest_items.append(
            {
                'id': info_page.id,
                'href': info_page.href,
                'media_type': 'application/xhtml+xml',
            }
        )
        spine_itemrefs.append({'idref': info_page.id, 'linear': True})
        for page in pages:
            manifest_items.append(
                {
                    'id': page.id,
                    'href': page.href,
                    'media_type': 'application/xhtml+xml',
                }
            )
            spine_itemrefs.append({'idref': page.id, 'linear': True})
        for image in images:
            manifest_items.append(image.model_dump())

        core = self.manifest.core

        content_id_str = core.id_.split(':')[-1]

        provider_ids = {
            'novel_id': content_id_str if 'pixiv.net' in core.id_ else None,
            'post_id': content_id_str if 'fanbox.cc' in core.id_ else None,
            'series_id': (
                core.isPartOf.identifier.split(':')[-1]
                if core.isPartOf and core.isPartOf.identifier
                else None
            ),
        }

        context = {
            'manifest': self.manifest,
            'provider_ids': provider_ids,
            'manifest_items': manifest_items,
            'spine_itemrefs': spine_itemrefs,
            'cover_image_id': cover_asset.id if cover_asset else None,
            'plain_description': plain_description,
        }
        return self._render_template('content.opf.j2', context)

    def _generate_nav(
        self, pages: list[PageAsset], info_page: PageAsset, has_cover: bool
    ) -> bytes:
        """nav.xhtml (目次) ファイルの内容を生成します。"""
        # 構造化された単一のコンテキスト辞書を作成
        nav_context = {
            'toc': {
                'has_info_page': True,
                'info_page': {
                    'title': info_page.title,
                    'href': info_page.href,  # info_page.href は "text/info.xhtml"
                },
                'pages': [{'href': page.href, 'title': page.title} for page in pages],
            },
            'landmarks': {
                'has_cover': has_cover,
                'info_page': {
                    'title': info_page.title,
                    'href': info_page.href,
                },
                # pages[0].href が存在する場合のみアクセスする
                'start_page_href': pages[0].href if pages else None,
            },
        }
        return self._render_template('nav.xhtml.j2', nav_context)
