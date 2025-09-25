# src/pixiv2epub/api.py

from pathlib import Path
from typing import Any, List, Optional

from .main import Pixiv2Epub

# --- 通常実行 (Download & Build) ---


def download_and_build_novel(
    novel_id: Any, config_path: Optional[str] = None, **kwargs
) -> Path:
    """単一のPixiv小説をダウンロードし、EPUBを生成します。"""
    cleanup_arg = kwargs.pop("cleanup", None)
    app = Pixiv2Epub(config_path=config_path, **kwargs)
    return app.run_novel(novel_id, cleanup=cleanup_arg)


def download_and_build_series(
    series_id: Any, config_path: Optional[str] = None, **kwargs
) -> List[Path]:
    """Pixivのシリーズをダウンロードし、EPUBを生成します。"""
    cleanup_arg = kwargs.pop("cleanup", None)
    app = Pixiv2Epub(config_path=config_path, **kwargs)
    return app.run_series(series_id, cleanup=cleanup_arg)


def download_and_build_user_novels(
    user_id: Any, config_path: Optional[str] = None, **kwargs
) -> List[Path]:
    """Pixivユーザーの全作品をダウンロードし、EPUBを生成します。"""
    cleanup_arg = kwargs.pop("cleanup", None)
    app = Pixiv2Epub(config_path=config_path, **kwargs)
    return app.run_user_novels(user_id, cleanup=cleanup_arg)


# --- 分割実行 ---


def download_novel(novel_id: Any, config_path: Optional[str] = None, **kwargs) -> Path:
    """単一の小説をダウンロードします。"""
    app = Pixiv2Epub(config_path=config_path, **kwargs)
    return app.download_novel(novel_id)


def download_series(
    series_id: Any, config_path: Optional[str] = None, **kwargs
) -> List[Path]:
    """シリーズ作品をダウンロードします。"""
    app = Pixiv2Epub(config_path=config_path, **kwargs)
    return app.download_series(series_id)


def download_user_novels(
    user_id: Any, config_path: Optional[str] = None, **kwargs
) -> List[Path]:
    """ユーザーの全作品をダウンロードします。"""
    app = Pixiv2Epub(config_path=config_path, **kwargs)
    return app.download_user_novels(user_id)


def build_novel(source_dir: Path, config_path: Optional[str] = None, **kwargs) -> Path:
    """ローカルのデータからEPUBを生成します。"""
    app = Pixiv2Epub(config_path=config_path, **kwargs)
    return app.build_from_directory(source_dir)
