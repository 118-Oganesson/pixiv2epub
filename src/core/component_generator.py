import datetime
import html
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

from ..data.models import EpubComponents, ImageAsset, NovelMetadata, PageAsset, PageInfo
from ..utils.path_manager import PathManager


class ComponentGenerator:
    """EPUBの構造ファイル(OPF, Nav)とXHTMLページの生成を担当します。

    収集されたアセット情報とメタデータを元に、Jinja2テンプレートを用いて
    EPUBを構成する各XML/XHTMLファイルを生成する責務を持ちます。
    """

    def __init__(self, config: Dict, metadata: NovelMetadata, paths: PathManager):
        """ComponentGeneratorのインスタンスを初期化します。

        Args:
            config (Dict): アプリケーション全体の設定情報。
            metadata (NovelMetadata): 小説のメタデータ。
            paths (PathManager): パス管理用のユーティリティインスタンス。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.metadata = metadata
        self.paths = paths
        self.css_file_rel_path = self.config.get("builder", {}).get(
            "css_file", "styles/style.css"
        )

        self.template_env = Environment(
            loader=FileSystemLoader("./templates/"),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        # テンプレート内でHTMLタグを除去するためのカスタムフィルタを登録
        self.template_env.filters["striptags"] = (
            lambda v: re.sub(r"<[^>]*?>", "", v) if v else ""
        )

    def generate_components(
        self,
        final_images: List[ImageAsset],
        raw_pages_info: List[PageInfo],
        cover_image_asset: Optional[ImageAsset],
    ) -> EpubComponents:
        """収集されたアセットを元に、EPUBの全構成要素を生成します。

        Args:
            final_images (List[ImageAsset]): EPUBに含める画像アセットのリスト。
            raw_pages_info (List[PageInfo]): 元となるページ情報のリスト。
            cover_image_asset (Optional[ImageAsset]): カバー画像アセット。

        Returns:
            EpubComponents: 生成された全コンポーネントを格納したデータクラス。
        """
        final_pages = self._create_final_pages(
            raw_pages_info, [img.filename for img in final_images]
        )
        self._recalculate_and_update_text_length(final_pages)
        info_page = self._build_info_page()
        cover_page = self._build_cover_page(cover_image_asset)

        manifest_items, spine_itemrefs = self._build_manifest_and_spine(
            final_pages, final_images, info_page, cover_page
        )

        content_opf = self._build_content_opf(
            manifest_items,
            spine_itemrefs,
            cover_image_asset.id if cover_image_asset else None,
        )
        nav_xhtml = self._build_nav_xhtml(
            final_pages, has_info_page=True, has_cover=bool(cover_image_asset)
        )

        css_path = self.paths.novel_dir / self.css_file_rel_path
        css_file_path = css_path if css_path.is_file() else None

        return EpubComponents(
            final_pages=final_pages,
            final_images=final_images,
            info_page=info_page,
            cover_page=cover_page,
            css_file_path=css_file_path,
            content_opf=content_opf,
            nav_xhtml=nav_xhtml,
        )

    def _create_final_pages(
        self, raw_pages_info: List[PageInfo], known_image_filenames: List[str]
    ) -> List[PageAsset]:
        """本文ファイル群を読み込み、最終的なXHTMLコンテンツを生成します。

        不完全なHTMLを完全なXHTML文書でラップし、画像パスをEPUB内の構造に合わせて修正します。

        Args:
            raw_pages_info (List[PageInfo]): 処理対象のページ情報リスト。
            known_image_filenames (List[str]): EPUBに含まれることが確定している画像ファイル名のリスト。

        Returns:
            List[PageAsset]: 処理済みのページアセットのリスト。
        """
        final_pages = []
        for i, p_info in enumerate(raw_pages_info, 1):
            page_file = self.paths.novel_dir / p_info.body_path.lstrip("./")
            if not page_file.is_file():
                self.logger.warning(f"ページファイルが見つかりません: {page_file}")
                continue

            try:
                content = page_file.read_text(encoding="utf-8")
                wrapped_content = self._ensure_xhtml_wrapper(content, p_info.title)
                fixed_content = self._fix_image_paths_in_xhtml(
                    wrapped_content, known_image_filenames
                )

                final_pages.append(
                    PageAsset(
                        id=f"page_{i}",
                        href=f"text/{page_file.name}",
                        content=fixed_content.encode("utf-8"),
                        title=p_info.title,
                    )
                )
            except Exception as e:
                self.logger.error(f"ページファイル'{page_file.name}'の処理に失敗: {e}")
        return final_pages

    def _build_info_page(self) -> PageAsset:
        """作品情報ページのXHTMLコンテンツを生成します。

        Returns:
            PageAsset: 生成された作品情報ページのページアセット。
        """
        template = self.template_env.get_template("info_page.xhtml.j2")

        parts = []
        if self.metadata.text_length:
            parts.append(f"文字数 {self.metadata.text_length:,} 文字")
        if self.metadata.date:
            parts.append(f"公開日 {self._format_date(self.metadata.date)}")

        novel_data = {
            "title": self.metadata.title,
            "author": self.metadata.authors.name,
            "description": self.metadata.description,
            "tags": self.metadata.tags,
            "meta_info": "　".join(parts),
            "source_url": self.metadata.original_source,
            "series_title": self.metadata.series.title
            if self.metadata.series
            else None,
        }

        rendered = template.render(
            title="作品情報", novel=novel_data, css_path=self.css_file_rel_path
        )
        return PageAsset(
            "info_page", "text/info.xhtml", rendered.encode("utf-8"), "作品情報"
        )

    def _build_cover_page(
        self, cover_image_asset: Optional[ImageAsset]
    ) -> Optional[PageAsset]:
        """カバーページのXHTMLコンテンツを生成します。

        Args:
            cover_image_asset (Optional[ImageAsset]):
                カバー画像のアセット。存在しない場合はNone。

        Returns:
            Optional[PageAsset]: 生成されたカバーページのページアセット。
                                 カバーが存在しない場合はNone。
        """
        if not cover_image_asset:
            return None
        template = self.template_env.get_template("cover_page.xhtml.j2")
        rendered = template.render(cover_image_href=cover_image_asset.href)
        return PageAsset(
            "cover_page", "text/cover.xhtml", rendered.encode("utf-8"), "カバー"
        )

    def _build_manifest_and_spine(
        self,
        final_pages: List[PageAsset],
        final_images: List[ImageAsset],
        info_page: PageAsset,
        cover_page: Optional[PageAsset],
    ) -> Tuple[List[Dict], List[Dict]]:
        """content.opf用のmanifestとspineの項目リストを構築します。

        Args:
            final_pages (List[PageAsset]): 全ての本文ページアセット。
            final_images (List[ImageAsset]): 全ての画像アセット。
            info_page (PageAsset): 作品情報ページのアセット。
            cover_page (Optional[PageAsset]): カバーページのアセット。

        Returns:
            Tuple[List[Dict], List[Dict]]: manifest項目リストとspine項目リストのタプル。
        """
        manifest_items = [
            {
                "id": "nav",
                "href": "nav.xhtml",
                "media_type": "application/xhtml+xml",
                "properties": "nav",
            }
        ]
        spine_itemrefs = []

        if cover_page:
            manifest_items.append(
                {
                    "id": cover_page.id,
                    "href": cover_page.href,
                    "media_type": "application/xhtml+xml",
                    "properties": "",
                }
            )
            # カバーは通常、本文とは別のフローで表示されるため linear="no" 相当の扱いとする
            spine_itemrefs.append({"idref": cover_page.id, "linear": False})

        manifest_items.append(
            {
                "id": info_page.id,
                "href": info_page.href,
                "media_type": "application/xhtml+xml",
                "properties": "",
            }
        )
        spine_itemrefs.append({"idref": info_page.id, "linear": True})

        manifest_items.extend(
            [
                {
                    "id": p.id,
                    "href": p.href,
                    "media_type": "application/xhtml+xml",
                    "properties": "",
                }
                for p in final_pages
            ]
        )
        spine_itemrefs.extend([{"idref": p.id, "linear": True} for p in final_pages])

        css_path = self.paths.novel_dir / self.css_file_rel_path
        if css_path.is_file():
            manifest_items.append(
                {
                    "id": "style",
                    "href": self.css_file_rel_path,
                    "media_type": "text/css",
                    "properties": "",
                }
            )

        manifest_items.extend(
            [
                {
                    "id": img.id,
                    "href": img.href,
                    "media_type": img.media_type,
                    "properties": img.properties,
                }
                for img in final_images
            ]
        )

        return manifest_items, spine_itemrefs

    def _build_content_opf(
        self,
        manifest_items: List[Dict],
        spine_itemrefs: List[Dict],
        cover_image_id: Optional[str],
    ) -> bytes:
        """content.opfファイルのコンテンツをテンプレートから生成します。

        Args:
            manifest_items (List[Dict]): manifestに記載する全アイテムのリスト。
            spine_itemrefs (List[Dict]): spineに記載する全アイテム参照のリスト。
            cover_image_id (Optional[str]): カバー画像のmanifest上のID。

        Returns:
            bytes: 生成されたcontent.opfのコンテンツ（UTF-8エンコード）。
        """
        template = self.template_env.get_template("content.opf.j2")

        context = {
            "metadata": self.metadata,
            "formatted_date": self._format_date(self.metadata.date),
            "modified_time": datetime.datetime.now(datetime.timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "cover_image_id": cover_image_id,
            "manifest_items": manifest_items,
            "spine_itemrefs": spine_itemrefs,
        }
        rendered = template.render(context)
        return rendered.encode("utf-8")

    def _build_nav_xhtml(
        self, pages: List[PageAsset], has_info_page: bool, has_cover: bool
    ) -> bytes:
        """nav.xhtml（目次ファイル）のコンテンツをテンプレートから生成します。

        Args:
            pages (List[PageAsset]): 目次に含める本文ページのリスト。
            has_info_page (bool): 作品情報ページが存在するかどうか。
            has_cover (bool): カバーページが存在するかどうか。

        Returns:
            bytes: 生成されたnav.xhtmlのコンテンツ（UTF-8エンコード）。
        """
        template = self.template_env.get_template("nav.xhtml.j2")
        rendered = template.render(
            pages=pages, has_info_page=has_info_page, has_cover=has_cover
        )
        return rendered.encode("utf-8")

    def _ensure_xhtml_wrapper(self, content: str, title: str) -> str:
        """コンテンツが<body>タグのみなどの断片である場合、完全なXHTML文書でラップします。

        EPUBの仕様に準拠するため、全てのコンテンツページが妥当なXHTMLである必要があります。

        Args:
            content (str): 元のHTMLコンテンツ。
            title (str): ページのタイトル。

        Returns:
            str: 必要に応じてラップされた、完全なXHTML文字列。
        """
        if "<html" in content.lower() and (
            "<head" in content.lower() or "<body" in content.lower()
        ):
            return content
        template = self.template_env.get_template("page_wrapper.xhtml.j2")
        return template.render(
            title=html.escape(title or "Page"),
            css_path=self.css_file_rel_path,
            content=content,
        )

    def _fix_image_paths_in_xhtml(
        self, content: str, known_image_filenames: List[str]
    ) -> str:
        """XHTML内の画像パスを、EPUBのディレクトリ構造に合わせた相対パスに修正します。

        例: `src="my_image.jpg"` -> `src="../images/my_image.jpg"`

        Args:
            content (str): 修正対象のXHTMLコンテンツ。
            known_image_filenames (List[str]): 有効な画像ファイル名のリスト。

        Returns:
            str: 画像パスが修正されたXHTMLコンテンツ。
        """

        def repl(match: re.Match) -> str:
            path = match.group(2).strip()
            # 絶対パスや親ディレクトリ参照を持つパスは、意図しない挙動を避けるため変更しない
            if path.startswith(("http", "/", "../")):
                return f'src="{path}"'

            image_filename = Path(path).name
            if image_filename not in known_image_filenames:
                self.logger.warning(
                    f"リンクされた画像ファイルが見つかりません: {image_filename}"
                )
            return f'src="../images/{image_filename}"'

        return re.sub(r'src=(["\'])([^"\']+)\1', repl, content, flags=re.IGNORECASE)

    def _format_date(self, date_str: str) -> str:
        """日付文字列を `YYYY-MM-DD` 形式に整形します。

        Args:
            date_str (str): ISO形式などの日付文字列。

        Returns:
            str: フォーマットされた日付文字列。失敗した場合は元の文字列の一部。
        """
        if not date_str:
            return ""
        try:
            dt = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return date_str.split("T")[0] if "T" in date_str else date_str

    def _recalculate_and_update_text_length(self, final_pages: List[PageAsset]):
        """最終的なページコンテンツからHTMLタグを除外し、正確な文字数を再計算してメタデータを更新します。

        Args:
            final_pages (List[PageAsset]): 最終的に生成されたページアセットのリスト。
        """
        self.logger.debug("ビルド内容から文字数を再計算しています...")
        total_length = 0
        for page in final_pages:
            soup = BeautifulSoup(page.content, "html.parser")
            text = soup.get_text(strip=True)
            total_length += len(text)

        original_length = self.metadata.text_length
        self.logger.debug(f"文字数: {original_length:,} -> {total_length:,}")

        self.metadata.text_length = total_length
