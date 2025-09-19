#
# -----------------------------------------------------------------------------
# pixiv2epub/src/pixiv2epub/providers/base_provider.py
#
# データソースプロバイダの基底クラス。
# この抽象クラスは、各データソース（例: Pixiv）から小説データを取得し、
# 後続のEPUBビルドプロセスで利用可能な統一された形式に変換するための
# 共通インターフェースを定義します。
# -----------------------------------------------------------------------------

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List


class BaseProvider(ABC):
    """
    データソースプロバイダの抽象基底クラス。

    各プロバイダは、特定のサイトから小説をダウンロードし、
    メタデータや本文、画像をローカルに保存する責務を持ちます。
    このクラスで定義されたメソッドを必ず実装する必要があります。
    """

    def __init__(self, config: Dict[str, Any]):
        """
        プロバイダの初期化。

        Args:
            config (Dict[str, Any]): アプリケーション全体の設定情報。
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"{self.__class__.__name__} を初期化しました。")

    @classmethod
    @abstractmethod
    def get_provider_name(cls) -> str:
        """
        プロバイダの名前を返すクラスメソッド。
        'pixiv', 'narou' のように小文字で返すことを想定します。

        Returns:
            str: プロバイダ名。
        """
        pass

    @abstractmethod
    def get_novel(self, novel_id: Any) -> Path:
        """
        単一の小説を取得し、ローカルに保存します。

        小説の本文、メタデータ、関連アセット（画像など）をダウンロードし、
        後続のビルドプロセスが利用できる形式で保存します。

        Args:
            novel_id (Any): 処理対象の小説を一意に識別するID。

        Returns:
            Path: ダウンロードされた小説データが格納されている
                  ディレクトリへのパス。
        """
        pass

    @abstractmethod
    def get_series(self, series_id: Any) -> List[Path]:
        """
        シリーズに含まれるすべての小説を取得し、ローカルに保存します。

        内部で `get_novel` を繰り返し呼び出すことが想定されます。

        Args:
            series_id (Any): 処理対象のシリーズを一意に識別するID。

        Returns:
            List[Path]: ダウンロードされた各小説のディレクトリパスのリスト。
        """
        pass

    @abstractmethod
    def get_user_novels(self, user_id: Any) -> List[Path]:
        """
        特定のユーザーが投稿したすべての小説を取得し、ローカルに保存します。

        Args:
            user_id (Any): 処理対象のユーザーを一意に識別するID。

        Returns:
            List[Path]: ダウンロードされた各小説のディレクトリパスのリスト。
        """
        pass
