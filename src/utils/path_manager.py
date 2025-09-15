from pathlib import Path


class PathManager:
    """
    小説ダウンロードに関するファイルパスの管理を専門に行うクラス。
    """

    def __init__(self, base_dir: Path, novel_title: str, novel_id: str):
        """
        PathManagerを初期化します。

        Args:
            base_dir (Path): 保存先のベースディレクトリ。
            novel_title (str): 小説のタイトル。
            novel_id (str): 小説ID。
        """
        # ファイル名として安全な文字列に変換
        safe_title = "".join(
            c for c in novel_title if c.isalnum() or c in " _-"
        ).strip()

        # タイトルが空、または記号のみだった場合のフォールバック
        if not safe_title:
            safe_title = f"novel_{novel_id}"

        self.novel_dir: Path = base_dir / safe_title
        self.image_dir: Path = self.novel_dir / "images"

    @property
    def detail_json_path(self) -> Path:
        """detail.json ファイルのパスを返すプロパティ。"""
        return self.novel_dir / "detail.json"

    def page_path(self, page_number: int) -> Path:
        """指定されたページ番号のXHTMLファイルパスを返します。"""
        return self.novel_dir / f"page-{page_number}.xhtml"

    def setup_directories(self) -> None:
        """保存に必要なディレクトリ（小説ルート、画像）を作成します。"""
        self.image_dir.mkdir(parents=True, exist_ok=True)
