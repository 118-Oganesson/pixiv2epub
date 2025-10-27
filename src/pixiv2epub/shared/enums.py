# src/pixiv2epub/shared/enums.py
from enum import Enum, auto


class Provider(Enum):
    """サポートされているコンテンツプロバイダー"""

    PIXIV = auto()
    FANBOX = auto()


class ContentType(Enum):
    """処理対象のコンテンツ種別"""

    WORK = auto()  # 単一の作品(小説、投稿など)
    SERIES = auto()  # 作品のシリーズ
    CREATOR = auto()  # クリエイターの全作品


class GuiStatus(str, Enum):
    """GUIのバックエンドとフロントエンド間の通信ステータス"""

    SUCCESS = 'success'
    ERROR = 'error'
