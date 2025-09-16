import logging
from rich.logging import RichHandler


def setup_logging(level="INFO"):
    """richライブラリを用いて、見やすく色付けされたログ出力を設定します。

    この関数を一度呼び出すと、アプリケーション全体の `logging` モジュールが
    設定されます。

    Args:
        level (str, optional): 出力するログのレベル。
            'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL' など。
            Defaults to "INFO".
    """
    logging.basicConfig(
        level=level,
        # richハンドラ側でフォーマットするため、ここではメッセージのみ渡す
        format="%(message)s",
        # richハンドラがタイムスタンプに使用するフォーマット
        datefmt="[%X]",
        handlers=[
            RichHandler(
                # エラー発生時にrich形式の美しいトレースバックを表示する
                rich_tracebacks=True,
                # ログ出力元のファイルパスを非表示にし、出力を簡潔にする
                show_path=False,
                # `[bold]` のようなマークアップをログメッセージ内で有効にする
                markup=True,
            )
        ],
    )
