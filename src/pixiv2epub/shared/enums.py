# src/pixiv2epub/shared/enums.py
from enum import Enum, auto


class Provider(str, Enum):
    """
    サポートされているコンテンツプロバイダー。
    strを継承することで、'=='による文字列比較とEnumの型安全性を両立する。
    """

    PIXIV = 'pixiv'
    FANBOX = 'fanbox'

    @classmethod
    def _missing_(cls, value: object) -> 'Provider | None':
        # 'PIXIV' のような大文字のキーでもアクセス可能にする
        for member in cls:
            if member.name == str(value).upper():
                return member
        return None


class ContentType(Enum):
    """処理対象のコンテンツ種別"""

    WORK = auto()  # 単一の作品(小説、投稿など)
    SERIES = auto()  # 作品のシリーズ
    CREATOR = auto()  # クリエイターの全作品


class GuiStatus(str, Enum):
    """GUIのバックエンドとフロントエンド間の通信ステータス"""

    SUCCESS = 'success'
    ERROR = 'error'
