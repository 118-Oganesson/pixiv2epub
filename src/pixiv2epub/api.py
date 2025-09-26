# src/pixiv2epub/api.py

from pathlib import Path
from typing import Any, List, Optional

from .app import Pixiv2Epub
from .core.settings import Settings


def _create_app(config_path: Optional[str] = None, **kwargs) -> Pixiv2Epub:
    """設定を読み込み、アプリケーションインスタンスを生成するヘルパー関数。"""
    settings = Settings(_config_file=config_path, **kwargs)
    return Pixiv2Epub(settings)


# --- 通常実行 (Download & Build) ---


def download_and_build_novel(
    novel_id: Any, config_path: Optional[str] = None, **kwargs
) -> Path:
    """単一のPixiv小説をダウンロードし、EPUBを生成します。"""
    app = _create_app(config_path, **kwargs)
    return app.run_novel(novel_id)


def download_and_build_series(
    series_id: Any, config_path: Optional[str] = None, **kwargs
) -> List[Path]:
    """Pixivのシリーズをダウンロードし、EPUBを生成します。"""
    app = _create_app(config_path, **kwargs)
    return app.run_series(series_id)


def download_and_build_user_novels(
    user_id: Any, config_path: Optional[str] = None, **kwargs
) -> List[Path]:
    """Pixivユーザーの全作品をダウンロードし、EPUBを生成します。"""
    app = _create_app(config_path, **kwargs)
    return app.run_user_novels(user_id)


# --- 分割実行 ---


def download_novel(novel_id: Any, config_path: Optional[str] = None, **kwargs) -> Path:
    """単一の小説をダウンロードします。"""
    app = _create_app(config_path, **kwargs)
    return app.download_novel(novel_id)


def download_series(
    series_id: Any, config_path: Optional[str] = None, **kwargs
) -> List[Path]:
    """シリーズ作品をダウンロードします。"""
    app = _create_app(config_path, **kwargs)
    return app.download_series(series_id)


def download_user_novels(
    user_id: Any, config_path: Optional[str] = None, **kwargs
) -> List[Path]:
    """ユーザーの全作品をダウンロードします。"""
    app = _create_app(config_path, **kwargs)
    return app.download_user_novels(user_id)


def build_novel(source_dir: Path, config_path: Optional[str] = None, **kwargs) -> Path:
    """ローカルのデータからEPUBを生成します。"""
    app = _create_app(config_path, **kwargs)
    return app.build_from_directory(source_dir)
