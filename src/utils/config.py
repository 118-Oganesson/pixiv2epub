import os
import tomllib
from typing import Any, Dict

DEFAULT_CONFIG_PATH = "./configs/config.toml"


def load_config(path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """
    TOML設定ファイルを読み込み、辞書として返します。
    環境変数 PIXIV_REFRESH_TOKEN があれば、設定を上書きします。
    """
    try:
        with open(path, "rb") as f:
            config = tomllib.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"設定ファイルが見つかりません: {path}")
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"設定ファイルの解析に失敗しました: {e}")

    # 環境変数で認証情報を上書き（推奨）
    if "PIXIV_REFRESH_TOKEN" in os.environ:
        config.setdefault("auth", {})["refresh_token"] = os.environ[
            "PIXIV_REFRESH_TOKEN"
        ]

    if not config.get("auth", {}).get("refresh_token"):
        raise ValueError(
            "Pixivのrefresh_tokenが設定ファイルまたは環境変数に見つかりません。"
        )

    return config
