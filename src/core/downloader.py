import re
import time
import json
import uuid
import logging
from pathlib import Path
from typing import Callable, Any, Dict, Optional, Set, List, Tuple, Union

from rich.progress import Progress
from rich.console import Console
from rich.prompt import Prompt
from pixivpy3 import AppPixivAPI, PixivError

from ..data.models import NovelApiResponse, NovelSeriesApiResponse
from ..utils.path_manager import PathManager

console = Console()


class PixivNovelDownloader:
    """
    特定の一つのPixiv小説をダウンロードし、整理して保存するクラス。
    インスタンスは単一の小説ダウンロードジョブを表します。
    """

    def __init__(
        self,
        novel_id: int,
        config: Dict[str, Any],
        override_base_dir: Optional[Path] = None,
    ):
        """
        PixivNovelDownloaderを初期化し、ダウンロードの準備を行います。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.novel_id = novel_id

        # --- 設定の読み込み ---
        downloader_conf = self.config.get("downloader", {})
        # override_base_dirが指定されていればそれを使用し、なければ設定ファイルの値を使用
        self.base_dir = override_base_dir or Path(
            downloader_conf.get("save_directory", "./pixiv_raw")
        )
        self.delay = float(downloader_conf.get("api_delay", 1.0))
        self.retry = int(downloader_conf.get("api_retries", 3))
        self.overwrite_images = bool(
            downloader_conf.get("overwrite_existing_images", False)
        )

        # --- APIクライアントの初期化 ---
        self.api = AppPixivAPI()
        refresh_token = self.config.get("auth", {}).get("refresh_token")
        if not refresh_token or refresh_token == "your_refresh_token_here":
            raise ValueError("設定に有効なPixivのrefresh_tokenが見つかりません。")
        self.api.auth(refresh_token=refresh_token)

        # --- データの取得 ---
        self.logger.debug(f"小説ID: {self.novel_id} の処理準備を開始します。")
        novel_data_dict = self._fetch_data(
            self.api.webview_novel, self.novel_id, "小説データ"
        )
        self.novel_data = NovelApiResponse.from_dict(novel_data_dict)
        self.detail_data_dict = self._fetch_data(
            self.api.novel_detail, self.novel_id, "詳細データ"
        )

        # ★ --- PathManagerの初期化ロジックを修正 ---
        template = downloader_conf.get("raw_dir_template", "{id}_{title}")

        # テンプレートで使用する変数を準備
        novel_detail = self.detail_data_dict.get("novel", {})
        template_vars = {
            "id": self.novel_data.id,
            "title": self.novel_data.title,
            "author_name": novel_detail.get("user", {}).get("name", "unknown_author"),
        }

        # テンプレートから相対パスを生成
        relative_path_str = template.format(**template_vars)

        # パスの各要素をサニタイズ
        invalid_chars = r'[\\/:*?"<>|]'
        safe_parts = [
            re.sub(invalid_chars, "_", part).strip()
            for part in relative_path_str.split("/")
        ]
        safe_dir_name = "/".join(safe_parts)

        self.paths = PathManager(
            base_dir=self.base_dir,
            novel_dir_name=safe_dir_name,  # サニタイズ済みのパス文字列を渡す
        )
        self.paths.setup_directories()
        self.logger.info(f"保存先ディレクトリ: {self.paths.novel_dir}")

        self.image_paths: Dict[str, str] = {}

    def run(self) -> Path:
        """
        初期化時に指定された小説のダウンロード処理全体を実行します。
        """
        self.logger.debug(
            f"小説「{self.novel_data.title}」のダウンロード処理を開始します。"
        )
        self._prepare_and_download_all_images()
        self._save_detail_json()
        self._save_pages()
        self.logger.debug("すべてのダウンロード処理が正常に完了しました。")
        return self.paths.novel_dir

    def _fetch_data(self, func: Callable, arg: Any, label: str) -> Dict:
        """Pixiv APIからデータを取得するための共通ラッパー関数。"""
        try:
            return func(arg)
        except PixivError as e:
            self.logger.error(f"{label}の取得に失敗しました: {e}")
            raise ValueError(f"{label}の取得に失敗しました。") from e
        except Exception as e:
            self.logger.critical(f"{label}の取得中に予期せぬエラー: {e}")
            raise RuntimeError(
                f"{label}の取得中に予期せぬエラーが発生しました。"
            ) from e

    def _safe_api_call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """API呼び出しをリトライロジック付きで安全に実行します。"""
        for attempt in range(1, self.retry + 1):
            try:
                result = func(*args, **kwargs)
                time.sleep(self.delay)
                return result
            except Exception as e:
                self.logger.warning(
                    f"API '{func.__name__}' 呼び出し中にエラー (試行 {attempt}/{self.retry}): {e}"
                )
                if attempt == self.retry:
                    self.logger.error(
                        f"API呼び出しが最終的に失敗しました: {func.__name__}"
                    )
                    raise
                time.sleep(self.delay * attempt)

        raise RuntimeError("API呼び出しがリトライ回数を超えました。")

    def _download_image(self, url: str, filename: str) -> Optional[str]:
        """指定されたURLから画像をダウンロードし、保存先の相対パスを返します。"""
        target_path = self.paths.image_dir / filename
        relative_path = f"./images/{filename}"

        if target_path.exists() and not self.overwrite_images:
            return relative_path

        try:
            self._safe_api_call(
                self.api.download, url, path=self.paths.image_dir, name=filename
            )
            return relative_path
        except Exception as e:
            # 警告やエラーは重要なので残す
            self.logger.warning(f"画像 ({url}) のダウンロードに失敗しました: {e}")
            return None

    def _prepare_and_download_all_images(self) -> None:
        text = self.novel_data.text
        uploaded_ids: Set[str] = set(re.findall(r"\[uploadedimage:(\d+)\]", text))
        pixiv_ids: Set[str] = set(re.findall(r"\[pixivimage:(\d+)\]", text))

        all_images = {f"u_{img_id}" for img_id in uploaded_ids} | {
            f"p_{ill_id}" for ill_id in pixiv_ids
        }

        with Progress() as progress:
            task = progress.add_task(
                "[cyan]Downloading images...", total=len(all_images)
            )

            # --- uploadedimage ---
            for image_id in uploaded_ids:
                filename = f"uploaded_{image_id}.png"  # 初期値
                if image_id in self.image_paths:
                    progress.update(
                        task, advance=1, description=f"[cyan]Skipped: {filename}"
                    )
                    continue

                image_meta = self.novel_data.images.get(image_id)
                if image_meta and image_meta.urls.original:
                    url = image_meta.urls.original
                    ext = url.split(".")[-1].split("?")[0]
                    filename = f"uploaded_{image_id}.{ext}"
                    path = self._download_image(url, filename)
                    if path:
                        self.image_paths[image_id] = path
                        progress.update(
                            task, advance=1, description=f"[green]Processed: {filename}"
                        )
                        continue

                progress.update(task, advance=1, description=f"[red]Failed: {filename}")

            # --- pixivimage ---
            for illust_id in pixiv_ids:
                filename = f"pixiv_{illust_id}.jpg"
                if illust_id in self.image_paths:
                    progress.update(
                        task, advance=1, description=f"[cyan]Skipped: {filename}"
                    )
                    continue

                try:
                    illust_resp = self._safe_api_call(
                        self.api.illust_detail, int(illust_id)
                    )
                    illust = illust_resp.get("illust", {})

                    url: Optional[str] = None
                    if illust.get("page_count", 1) == 1:
                        url = illust.get("meta_single_page", {}).get(
                            "original_image_url"
                        )
                    else:
                        pages = illust.get("meta_pages", [])
                        if pages:
                            url = pages[0].get("image_urls", {}).get("original")

                    if url:
                        ext = url.split(".")[-1].split("?")[0]
                        filename = f"pixiv_{illust_id}.{ext}"
                        path = self._download_image(url, filename)
                        if path:
                            self.image_paths[illust_id] = path
                            progress.update(
                                task,
                                advance=1,
                                description=f"[green]Processed: {filename}",
                            )
                            continue

                    progress.update(
                        task, advance=1, description=f"[red]Failed: {filename}"
                    )

                except Exception as e:
                    self.logger.warning(f"イラスト {illust_id} の取得に失敗: {e}")
                    progress.update(
                        task, advance=1, description=f"[red]Failed: {filename}"
                    )

        self.logger.debug("画像ダウンロード処理が完了しました。")

    def _download_cover_image(self, novel: Dict) -> Optional[str]:
        """小説のカバー画像をダウンロードし、保存先の相対パスを返します。"""
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

    def _get_tag_replacement_strategies(
        self,
    ) -> List[Tuple[re.Pattern, Union[str, Callable]]]:
        """
        Pixiv独自タグを置換するためのルール（ストラテジー）のリストを返します。

        Returns:
            List[Tuple[re.Pattern, Union[str, Callable]]]: (正規表現オブジェクト, 置換文字列または関数) のタプルのリスト。
        """
        return [
            # 画像タグ: [uploadedimage:id] or [pixivimage:id] -> <img ... />
            (
                re.compile(r"\[(uploadedimage|pixivimage):(\d+)\]"),
                self._replace_image_tag,
            ),
            # ページジャンプタグ: [jump:id] -> <a ...>
            (re.compile(r"\[jump:(\d+)\]"), r'<a href="page-\1.xhtml">\1ページへ</a>'),
            # 章タイトルタグ: [chapter:title] -> <h2>...</h2>
            (re.compile(r"\[chapter:(.+?)\]"), r"<h2>\1</h2>"),
            # ルビタグ: [[rb:漢字 > ふりがな]] -> <ruby>...</ruby>
            (
                re.compile(r"\[\[rb:(.+?)\s*>\s*(.+?)\]\]"),
                r"<ruby>\1<rt>\2</rt></ruby>",
            ),
            # 外部リンクタグ: [[jumpuri:text > url]] -> <a ...>
            (
                re.compile(r"\[\[jumpuri:(.+?)\s*>\s*(https?://.+?)\]\]"),
                r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
            ),
        ]

    def _replace_image_tag(self, match: re.Match) -> str:
        """
        画像タグ `[uploadedimage:id]` または `[pixivimage:id]` を置換するためのヘルパー関数。

        Args:
            match (re.Match): 正規表現のマッチオブジェクト。

        Returns:
            str: 置換後のHTML文字列 (`<img ... />`) または元のタグ文字列。
        """
        tag_type = match.group(1).replace("image", "")  # "uploaded" or "pixiv"
        image_id = match.group(2)

        # 挿絵画像とイラスト画像でID空間が異なる可能性があるため、
        # `image_paths`のキーを `uploaded_123` のように一意にする方法も考えられるが、
        # 現在の実装ではIDの重複がないため、このままとする。
        path = self.image_paths.get(image_id)

        if path:
            return f'<img alt="{tag_type}_{image_id}" src="{path}" />'

        # 画像が見つからなかった場合は、元のタグをそのまま返す
        self.logger.warning(
            f"置換対象の画像ID '{image_id}' のパスが見つかりませんでした。"
        )
        return match.group(0)

    def _replace_tags(self, text: str) -> str:
        """
        小説本文に含まれるPixiv特有のタグを、定義されたストラテジーに従ってHTMLタグに置換します。
        """
        strategies = self._get_tag_replacement_strategies()
        for pattern, replacement in strategies:
            text = pattern.sub(replacement, text)

        return text.replace("\n", "<br />\n")

    def _save_pages(self) -> None:
        """小説本文をページごとに分割し、.xhtml ファイルとして保存します。"""
        self.logger.debug("本文ページの保存を開始します。")
        text = self._replace_tags(self.novel_data.text)
        pages = text.split("[newpage]")
        for i, page_content in enumerate(pages):
            filename = self.paths.page_path(i + 1)
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(page_content)
            except IOError as e:
                self.logger.error(f"ページ {i + 1} の保存に失敗しました: {e}")
        self.logger.debug(f"{len(pages)}ページの保存が完了しました。")

    def _save_detail_json(self) -> None:
        """小説のメタデータを抽出し、'detail.json' として保存します。"""
        self.logger.debug("詳細情報(detail.json)の作成と保存を開始します。")
        novel = self.detail_data_dict.get("novel", {})
        cover_path = self._download_cover_image(novel)

        def extract_page_title(page_content: str, page_number: int) -> str:
            match = re.search(r"<h2>(.*?)</h2>", page_content)
            return match.group(1) if match else f"ページ {page_number}"

        text = self._replace_tags(self.novel_data.text)
        pages_content = text.split("[newpage]")
        pages_data = [
            {
                "title": extract_page_title(content, i + 1),
                "body": f"./page-{i + 1}.xhtml",
            }
            for i, content in enumerate(pages_content)
        ]

        detail_summary = {
            "title": novel.get("title"),
            "authors": {
                "name": novel.get("user", {}).get("name"),
                "id": novel.get("user", {}).get("id"),
            },
            "language": "ja",
            "series": novel.get("series"),
            "publisher": "pixiv",
            "description": novel.get("caption"),
            "identifier": {
                "novel_id": novel.get("id"),
                "uuid": f"urn:uuid:{uuid.uuid4()}",
            },
            "date": novel.get("create_date"),
            "cover": cover_path,
            "tags": [t.get("name") for t in novel.get("tags", [])],
            "original_source": f"https://www.pixiv.net/novel/show.php?id={novel.get('id')}",
            "pages": pages_data,
            "x_meta": {"text_length": novel.get("text_length")},
        }
        try:
            with open(self.paths.detail_json_path, "w", encoding="utf-8") as f:
                json.dump(detail_summary, f, ensure_ascii=False, indent=2)
            self.logger.debug("detail.json の保存が完了しました。")
        except IOError as e:
            self.logger.error(f"detail.json の保存に失敗しました: {e}")


class PixivSeriesDownloader:
    """
    特定のPixiv小説シリーズをダウンロードし、整理して保存するクラス。
    シリーズ用の親ディレクトリを作成し、その中に各小説のデータをダウンロードします。
    """

    def __init__(self, series_id: int, config: Dict[str, Any]):
        """PixivSeriesDownloaderを初期化します。"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.series_id = series_id

        # --- 設定の読み込み ---
        downloader_conf = self.config.get("downloader", {})
        self.base_dir = Path(downloader_conf.get("save_directory", "./pixiv_raw"))

        # --- APIクライアントの初期化 ---
        self.api = AppPixivAPI()
        refresh_token = self.config.get("auth", {}).get("refresh_token")
        if not refresh_token or refresh_token == "your_refresh_token_here":
            raise ValueError("設定に有効なPixivのrefresh_tokenが見つかりません。")
        self.api.auth(refresh_token=refresh_token)

        # --- シリーズ情報の取得 ---
        self.logger.debug(f"シリーズID: {self.series_id} の情報取得を開始します。")
        series_data_dict = self.api.novel_series(series_id=self.series_id)
        self.series_data = NovelSeriesApiResponse.from_dict(series_data_dict)

        # ★ --- 保存先ディレクトリの決定ロジックを修正 ---
        template = downloader_conf.get("series_dir_template", "series_{id}_{title}")

        # テンプレートで使用する変数を準備
        template_vars = {
            "id": self.series_data.detail.id,
            "title": self.series_data.detail.title,
            "author_name": self.series_data.detail.user.name,
        }

        # テンプレートから相対パスを生成
        relative_path_str = template.format(**template_vars)

        # パスの各要素をサニタイズ
        invalid_chars = r'[\\/:*?"<>|]'
        safe_parts = [
            re.sub(invalid_chars, "_", part).strip()
            for part in relative_path_str.split("/")
        ]
        safe_dir_name = Path(*safe_parts)  # Pathオブジェクトに変換

        self.series_dir = self.base_dir / safe_dir_name
        self.series_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"シリーズ保存先ディレクトリ: {self.series_dir}")

    def run(self, interactive: bool = False) -> List[Path]:
        """シリーズのダウンロード処理を実行し、ダウンロード先のパスリストを返します。"""
        downloaded_paths = []  # ダウンロードしたパスを保存するリスト
        if interactive:
            novel_ids_to_download = self._select_novels_interactive()
            if not novel_ids_to_download:
                self.logger.info(
                    "ダウンロード対象が選択されなかったため、処理を終了します。"
                )
                return downloaded_paths
        else:
            novel_ids_to_download = [novel.id for novel in self.series_data.novels]

        total = len(novel_ids_to_download)
        self.logger.info(
            f"計 {total} 件の小説をシリーズフォルダ内にダウンロードします。"
        )

        for i, novel_id in enumerate(novel_ids_to_download, 1):
            console.rule(f"[bold]Processing Novel {i}/{total} (ID: {novel_id})[/]")
            try:
                # override_base_dir を使用して、保存先をシリーズディレクトリに指定
                downloader = PixivNovelDownloader(
                    novel_id=novel_id,
                    config=self.config,
                    override_base_dir=self.series_dir,
                )
                novel_path = downloader.run()
                downloaded_paths.append(novel_path)  # 成功したパスを追加
            except Exception as e:
                self.logger.error(
                    f"小説ID {novel_id} のダウンロードに失敗しました: {e}",
                    exc_info=True,
                )
                console.print(f"❌ [red]小説ID {novel_id} の処理に失敗しました。[/]")

        console.print(
            f"\n✅ [bold green]シリーズ「{self.series_data.detail.title}」のダウンロードが完了しました。[/]"
        )
        return downloaded_paths

    def _select_novels_interactive(self) -> List[int]:
        """対話モードでダウンロードする小説を選択させます。"""
        console.print("\n[cyan]-- ダウンロード対象の小説を選択 --[/]")
        novels = sorted(self.series_data.novels, key=lambda n: n.order)

        for i, novel in enumerate(novels):
            console.print(f"[bold white]{i + 1: >2}[/]: {novel.title}")

        console.print("\nダウンロードする小説の番号を入力してください。")
        console.print("[dim]例: '1, 3, 5-8' or 'all'[/]")

        while True:
            try:
                choice = Prompt.ask("[bold]番号[/]")
                if choice.lower() == "all":
                    return [novel.id for novel in novels]

                selected_indices = set()
                parts = choice.replace(" ", "").split(",")
                for part in parts:
                    if "-" in part:
                        start, end = map(int, part.split("-"))
                        selected_indices.update(range(start - 1, end))
                    else:
                        selected_indices.add(int(part) - 1)

                return [
                    novels[i].id
                    for i in sorted(list(selected_indices))
                    if 0 <= i < len(novels)
                ]
            except (ValueError, IndexError):
                console.print("[red]無効な入力です。もう一度入力してください。[/]")
