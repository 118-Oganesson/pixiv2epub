#
# -----------------------------------------------------------------------------
# pixiv2epub/src/pixiv2epub/api.py
#
# このモジュールは、pixiv2epubをライブラリとして利用するための高レベルな公開APIを
# 提供します（Facade パターン）。
# 外部のPythonスクリプトから複雑な内部構造を意識することなく、主要な機能を
# 簡単な関数呼び出しで利用できるように設計されています。
# -----------------------------------------------------------------------------

import logging
from pathlib import Path
from typing import Any, List, Optional

from .orchestration.coordinator import Coordinator
from .utils.config_loader import load_config
from .utils.logging_setup import setup_logging


logger = logging.getLogger(__name__)


def download_and_build_novel(
    novel_id: Any,
    config_path: Optional[str] = None,
    log_level: str = "INFO",
) -> Path:
    """
    単一のPixiv小説をダウンロードし、EPUBファイルとして生成します。

    Args:
        novel_id (Any): Pixivの小説ID。
        config_path (Optional[str]): カスタム設定ファイルのパス。
                                     Noneの場合はデフォルトパスが使用されます。
        log_level (str): 出力するログのレベル ('INFO', 'DEBUG'など)。

    Returns:
        Path: 生成されたEPUBファイルのパス。
    """
    setup_logging(log_level)
    config = load_config(config_path) if config_path else load_config()

    coordinator = Coordinator(config)
    # 現時点ではproviderとbuilderは固定だが、将来的には引数で指定可能に
    return coordinator.download_and_build_novel(
        provider_name="pixiv", builder_name="epub", novel_id=novel_id
    )


def download_and_build_series(
    series_id: Any,
    config_path: Optional[str] = None,
    log_level: str = "INFO",
) -> List[Path]:
    """
    Pixivの小説シリーズをダウンロードし、各作品をEPUBファイルとして生成します。

    Args:
        series_id (Any): PixivのシリーズID。
        config_path (Optional[str]): カスタム設定ファイルのパス。
        log_level (str): 出力するログのレベル。

    Returns:
        List[Path]: 生成されたEPUBファイルのパスのリスト。
    """
    setup_logging(log_level)
    config = load_config(config_path) if config_path else load_config()

    coordinator = Coordinator(config)
    return coordinator.download_and_build_series(
        provider_name="pixiv", builder_name="epub", series_id=series_id
    )


def download_and_build_user_novels(
    user_id: Any,
    config_path: Optional[str] = None,
    log_level: str = "INFO",
) -> List[Path]:
    """
    特定のPixivユーザーの全小説をダウンロードし、各作品をEPUBファイルとして生成します。

    Args:
        user_id (Any): PixivのユーザーID。
        config_path (Optional[str]): カスタム設定ファイルのパス。
        log_level (str): 出力するログのレベル。

    Returns:
        List[Path]: 生成されたEPUBファイルのパスのリスト。
    """
    setup_logging(log_level)
    config = load_config(config_path) if config_path else load_config()

    coordinator = Coordinator(config)
    return coordinator.download_and_build_user_novels(
        provider_name="pixiv", builder_name="epub", user_id=user_id
    )
