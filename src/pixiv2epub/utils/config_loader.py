#
# -----------------------------------------------------------------------------
# src/pixiv2epub/utils/config_loader.py
#
# アプリケーションの設定をTOMLファイルから読み込む機能を提供します。
# 環境変数からの設定上書きにも対応し、柔軟な設定管理を実現します。
# -----------------------------------------------------------------------------
import os
import tomllib
from typing import Any, Dict

DEFAULT_CONFIG_PATH = "./configs/config.toml"


def load_config(path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """TOML設定ファイルを読み込み、辞書として返します。

    環境変数 `PIXIV_REFRESH_TOKEN` が設定されている場合、
    ファイル内の設定よりも優先して認証情報として使用します。

    Args:
        path (str, optional): 読み込む設定ファイルのパス。
            Defaults to DEFAULT_CONFIG_PATH.

    Returns:
        Dict[str, Any]: 読み込まれた設定情報の辞書。

    Raises:
        FileNotFoundError: 指定されたパスに設定ファイルが見つからない場合。
        ValueError: 設定ファイルの解析に失敗した場合、または
            `refresh_token` が設定ファイルにも環境変数にも見つからない場合。
    """
    try:
        with open(path, "rb") as f:
            config = tomllib.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"設定ファイルが見つかりません: {path}")
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"設定ファイルの解析に失敗しました: {e}")

    # 環境変数からの認証情報の上書きは、トークンをコードやファイルに
    # 直接記述することを避けるための推奨される方法です。
    if "PIXIV_REFRESH_TOKEN" in os.environ:
        config.setdefault("auth", {})["refresh_token"] = os.environ[
            "PIXIV_REFRESH_TOKEN"
        ]

    if not config.get("auth", {}).get("refresh_token"):
        raise ValueError(
            "Pixivのrefresh_tokenが設定ファイルまたは環境変数に見つかりません。"
        )

    return config
