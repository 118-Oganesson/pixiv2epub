#
# -----------------------------------------------------------------------------
# src/pixiv2epub/utils/path_manager.py
#
# ファイルシステムのパス操作を抽象化し、一元管理する機能を提供します。
# ファイル名として不正な文字をサニタイズ（無害化）する機能や、
# 特定の小説に関連するファイルパスを一貫したルールで生成する責務を持ちます。
# -----------------------------------------------------------------------------
import re
from pathlib import Path
from typing import Any, Dict

from .. import constants as const


def sanitize_path_part(part: str) -> str:
    """
    ファイル/ディレクトリ名として安全でない文字を'_'に置換します。

    Args:
        part (str): サニタイズ対象の文字列（パスの一部）。

    Returns:
        str: サニタイズ後の文字列。
    """
    return re.sub(const.INVALID_PATH_CHARS_REGEX, "_", part).strip()


def generate_sanitized_path(template: str, variables: Dict[str, Any]) -> Path:
    """
    テンプレートと変数からパス文字列を生成し、各部分をサニタイズします。

    Args:
        template (str): "{author_name}/{title}" のようなフォーマット文字列。
        variables (Dict[str, Any]): テンプレートに埋め込む変数。

    Returns:
        Path: サニタイズされた相対パス。
    """
    # 存在しないキーがあってもエラーにならないように、値がNoneの場合は空文字に置換
    safe_vars = {k: v or "" for k, v in variables.items()}
    relative_path_str = template.format_map(safe_vars)

    # パスを分割し、各要素をサニタイズしてからPathオブジェクトとして再結合する
    safe_parts = [sanitize_path_part(part) for part in Path(relative_path_str).parts]
    return Path(*safe_parts)


class PathManager:
    """小説の各種ファイルを管理するためのパス操作をまとめたクラス。

    小説ごとに生成されるディレクトリや、その中の各種ファイルへのパスを
    一元的に管理し、一貫性のあるパス操作を提供します。
    """

    def __init__(self, base_dir: Path, novel_dir_name: str):
        """PathManagerを初期化します。

        Args:
            base_dir (Path): すべての小説が保存されるルートディレクトリ。
            novel_dir_name (str): `base_dir`内に作成される、
                このインスタンスが管理する小説固有のディレクトリ名。
                空文字が渡された場合は 'novel_unknown' を使用します。
        """
        # ディレクトリ名が指定されていない場合、予期せぬエラーを防ぐために
        # デフォルトのディレクトリ名を設定する。
        if not novel_dir_name:
            novel_dir_name = "novel_unknown"

        self.novel_dir: Path = base_dir / novel_dir_name
        self.image_dir: Path = self.novel_dir / "images"

    @property
    def detail_json_path(self) -> Path:
        """小説のメタデータを格納する `detail.json` ファイルのパス。"""
        return self.novel_dir / "detail.json"

    def page_path(self, page_number: int) -> Path:
        """指定されたページ番号に対応するXHTMLファイルのパスを生成します。

        Args:
            page_number (int): ページの番号。

        Returns:
            Path: ページファイルへのPathオブジェクト。
        """
        return self.novel_dir / f"page-{page_number}.xhtml"

    def setup_directories(self) -> None:
        """小説ファイルと画像ファイルを保存するためのディレクトリを作成します。

        `exist_ok=True` を指定しているため、ディレクトリが既に存在していても
        エラーは発生しません。
        """
        self.image_dir.mkdir(parents=True, exist_ok=True)
