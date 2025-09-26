# src/pixiv2epub/utils/path_manager.py

import re
from pathlib import Path
from typing import Any, Dict

from .. import constants as const


def sanitize_path_part(part: str) -> str:
    """ファイル/ディレクトリ名として安全でない文字を'_'に置換します。"""
    return re.sub(const.INVALID_PATH_CHARS_REGEX, "_", part).strip()


def generate_sanitized_path(template: str, variables: Dict[str, Any]) -> Path:
    """テンプレートと変数からパス文字列を生成し、各部分をサニタイズします。"""
    safe_vars = {k: v or "" for k, v in variables.items()}
    relative_path_str = template.format_map(safe_vars)
    safe_parts = [sanitize_path_part(part) for part in Path(relative_path_str).parts]
    return Path(*safe_parts)


class PathManager:
    """小説の各種ファイルを管理するためのパス操作をまとめたクラス。"""

    def __init__(self, base_dir: Path, novel_dir_name: str):
        if not novel_dir_name:
            novel_dir_name = const.UNKNOWN_NOVEL_DIR

        self.novel_dir: Path = base_dir / novel_dir_name
        self.image_dir: Path = self.novel_dir / const.IMAGES_DIR_NAME

    @property
    def detail_json_path(self) -> Path:
        """小説のメタデータを格納する `detail.json` ファイルのパス。"""
        return self.novel_dir / const.DETAIL_FILE_NAME

    def page_path(self, page_number: int) -> Path:
        """指定されたページ番号に対応するXHTMLファイルのパスを生成します。"""
        return self.novel_dir / f"page-{page_number}.xhtml"

    def setup_directories(self) -> None:
        """小説ファイルと画像ファイルを保存するためのディレクトリを作成します。"""
        self.image_dir.mkdir(parents=True, exist_ok=True)
