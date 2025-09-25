#
# -----------------------------------------------------------------------------
# pixiv2epub/src/pixiv2epub/providers/pixiv/persister.py
#
# Pixivから取得したデータをローカルファイルシステムに永続化する責務を持つクラス。
# 画像のダウンロード、メタデータ(detail.json)の生成、本文(XHTML)の保存を担当する。
# -----------------------------------------------------------------------------
import json
import logging
import re
import uuid
from datetime import datetime
from dataclasses import asdict
from typing import Any, Dict, Optional

from ... import constants as const
from ...data_models import (
    Author,
    NovelApiResponse,
    NovelMetadata,
    PageInfo,
    SeriesInfo,
)
from ...utils.path_manager import PathManager
from .api_client import PixivApiClient
from .parser import PixivParser


class PixivDataPersister:
    """APIから取得した小説データをファイルとして保存するクラス。"""

    def __init__(
        self,
        config: Dict[str, Any],
        paths: PathManager,
        api_client: PixivApiClient,
    ):
        """
        PixivDataPersisterを初期化します。

        Args:
            config (Dict[str, Any]): アプリケーション設定。
            paths (PathManager): ファイルパスを管理するインスタンス。
            api_client (PixivApiClient): 画像ダウンロードに使用するAPIクライアント。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.paths = paths
        self.api_client = api_client
        self.overwrite_images = bool(
            self.config.get(const.KEY_DOWNLOADER, {}).get(
                const.KEY_OVERWRITE_IMAGES, False
            )
        )
        self.image_paths: Dict[str, str] = {}
        self.parser = PixivParser(self.image_paths)

    def persist(self, novel_data: NovelApiResponse, detail_data_dict: Dict[str, Any]):
        """
        一連の保存処理を実行するメインメソッド。

        Args:
            novel_data (NovelApiResponse): webview_novel APIからのデータ。
            detail_data_dict (Dict[str, Any]): novel_detail APIからのデータ。
        """
        self.logger.debug(f"永続化処理を開始します: {self.paths.novel_dir}")
        self._prepare_and_download_all_images(novel_data)
        self._save_detail_json(novel_data, detail_data_dict)
        self._save_pages(novel_data)
        self.logger.debug("永続化処理が完了しました。")

    def _download_image(self, url: str, filename: str) -> Optional[str]:
        """単一の画像をダウンロードし、メタデータ用の相対パスを返します。"""
        target_path = self.paths.image_dir / filename
        relative_path_for_meta = f"./{const.IMAGES_DIR_NAME}/{filename}"

        if target_path.exists() and not self.overwrite_images:
            return relative_path_for_meta

        try:
            self.api_client.download(url, path=self.paths.image_dir, name=filename)
            return relative_path_for_meta
        except Exception as e:
            self.logger.warning(f"画像 ({url}) のダウンロードに失敗しました: {e}")
            return None

    def _prepare_and_download_all_images(self, novel_data: NovelApiResponse):
        """本文中のすべての画像をダウンロードします。"""
        self.logger.info("画像のダウンロードを開始します...")
        text = novel_data.text
        uploaded_ids = set(re.findall(r"\[uploadedimage:(\d+)\]", text))
        pixiv_ids = set(re.findall(r"\[pixivimage:(\d+)\]", text))

        total_images = len(uploaded_ids) + len(pixiv_ids)
        self.logger.info(f"対象画像: {total_images}件")

        for image_id in uploaded_ids:
            image_meta = novel_data.images.get(image_id)
            if image_meta and image_meta.urls.original:
                url = image_meta.urls.original
                ext = url.split(".")[-1].split("?")[0]
                filename = f"uploaded_{image_id}.{ext}"
                if path := self._download_image(url, filename):
                    self.image_paths[image_id] = path

        for illust_id in pixiv_ids:
            try:
                illust_resp = self.api_client.illust_detail(int(illust_id))
                illust = illust_resp.get("illust", {})
                url: Optional[str] = (
                    illust.get("meta_single_page", {}).get("original_image_url")
                    if illust.get("page_count", 1) == 1
                    else (
                        illust.get("meta_pages", [{}])[0]
                        .get("image_urls", {})
                        .get("original")
                    )
                )
                if url:
                    ext = url.split(".")[-1].split("?")[0]
                    filename = f"pixiv_{illust_id}.{ext}"
                    if path := self._download_image(url, filename):
                        self.image_paths[illust_id] = path
            except Exception as e:
                self.logger.warning(f"イラスト {illust_id} の取得に失敗: {e}")

        self.logger.info("画像ダウンロード処理が完了しました。")

    def _download_cover_image(self, novel: Dict) -> Optional[str]:
        """小説の表紙画像をダウンロードします。"""
        cover_url = novel.get("image_urls", {}).get("large")
        if not cover_url:
            self.logger.info("この小説にはカバー画像がありません。")
            return None

        def convert_url(url: str) -> str:
            return re.sub(r"/c/\d+x\d+(?:_\d+)?/", "/c/600x600/", url)

        ext = cover_url.split(".")[-1].split("?")[0]
        cover_filename = f"cover.{ext}"

        for url in (convert_url(cover_url), cover_url):
            if path := self._download_image(url, cover_filename):
                return path

        self.logger.error("カバー画像のダウンロードに最終的に失敗しました。")
        return None

    def _save_pages(self, novel_data: NovelApiResponse):
        """小説本文をページごとに分割し、XHTMLファイルとして保存します。"""
        text = self.parser.parse(novel_data.text)
        pages = text.split("[newpage]")
        for i, page_content in enumerate(pages):
            filename = self.paths.page_path(i + 1)
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page_content)
            except IOError as e:
                self.logger.error(f"ページ {i + 1} の保存に失敗しました: {e}")
        self.logger.debug(f"{len(pages)}ページの保存が完了しました。")

    def _save_detail_json(self, novel_data: NovelApiResponse, detail_data_dict: Dict):
        """
        小説のメタデータを抽出し、'detail.json'として保存します。
        NovelMetadataオブジェクトを構築し、それを直接辞書に変換して保存します。
        """
        novel = detail_data_dict.get("novel", {})

        # 1. 関連データを準備
        cover_path = self._download_cover_image(novel)
        text = self.parser.parse(novel_data.text)
        pages_content = text.split("[newpage]")
        parsed_description = self.parser.parse(novel.get("caption", ""))

        # 日付文字列をパースして YYYY年MM月DD日 HH:MM 形式にフォーマット
        formatted_date = ""
        raw_date = novel.get("create_date")
        if raw_date:
            try:
                dt_object = datetime.fromisoformat(raw_date)
                formatted_date = dt_object.strftime("%Y年%m月%d日 %H:%M")
            except (ValueError, TypeError):
                self.logger.warning(f"日付形式の解析に失敗しました: {raw_date}")
                formatted_date = raw_date

        # 2. ネストされたデータモデルを先に構築
        author_info = Author(
            name=novel.get("user", {}).get("name"), id=novel.get("user", {}).get("id")
        )
        pages_info = [
            PageInfo(
                title=self.parser.extract_page_title(content, i + 1),
                body=f"./page-{i + 1}.xhtml",
            )
            for i, content in enumerate(pages_content)
        ]
        series_info = SeriesInfo.from_dict(novel.get("series"))

        # 3. NovelMetadata インスタンスを生成
        metadata = NovelMetadata(
            title=novel.get("title"),
            authors=author_info,
            series=series_info,
            description=parsed_description,
            identifier={
                "novel_id": novel.get("id"),
                "uuid": f"urn:uuid:{uuid.uuid4()}",
            },
            date=formatted_date,  # フォーマットした日付を使用
            cover_path=cover_path,
            tags=[t.get("name") for t in novel.get("tags", [])],
            original_source=const.PIXIV_NOVEL_URL.format(novel_id=novel.get("id")),
            pages=pages_info,
            text_length=novel.get("text_length"),
        )

        # 4. データクラスを辞書に変換してJSONとして直接保存 (変更なし)
        try:
            metadata_dict = asdict(metadata)
            with open(self.paths.detail_json_path, "w", encoding="utf-8") as f:
                json.dump(metadata_dict, f, ensure_ascii=False, indent=2)
            self.logger.debug("detail.json の保存が完了しました。")
        except IOError as e:
            self.logger.error(f"detail.json の保存に失敗しました: {e}")
