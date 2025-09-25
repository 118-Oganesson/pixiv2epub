# src/pixiv2epub/utils/config.py

import os
import tomllib
from typing import Any, Dict

from ..exceptions import ConfigError

DEFAULT_CONFIG_PATH = "./configs/config.toml"


def load_config(path: str = None) -> Dict[str, Any]:
    """
    TOML設定ファイルを読み込み、環境変数で上書きして辞書として返します。

    Args:
        path (str, optional): 読み込む設定ファイルのパス。
            Noneの場合はデフォルトパスが使用されます。

    Returns:
        Dict[str, Any]: 読み込まれた設定情報の辞書。

    Raises:
        ConfigError: ファイルが見つからない、解析に失敗した場合、または
                     `refresh_token` が見つからない場合。
    """
    config_path = path or DEFAULT_CONFIG_PATH
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"設定ファイルが見つかりません: {config_path}")
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"設定ファイルの解析に失敗しました: {e}")

    # 環境変数 PIXIV_REFRESH_TOKEN があれば設定を上書き
    if "PIXIV_REFRESH_TOKEN" in os.environ:
        config.setdefault("auth", {})["refresh_token"] = os.environ[
            "PIXIV_REFRESH_TOKEN"
        ]

    if not config.get("auth", {}).get("refresh_token"):
        raise ConfigError(
            "Pixivのrefresh_tokenが設定ファイルまたは環境変数に見つかりません。"
        )

    return config
