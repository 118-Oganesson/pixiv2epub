import logging
from rich.logging import RichHandler


def setup_logging(level="INFO"):
    """
    richライブラリを使用して、ログ出力を美しく設定します。
    すべてのログ出力がこの設定に従います。
    """
    logging.basicConfig(
        level=level,
        format="%(message)s",  # rich側でフォーマットするためメッセージのみ渡す
        datefmt="[%X]",  # richがタイムスタンプに使用するフォーマット
        handlers=[
            RichHandler(
                rich_tracebacks=True,  # エラー発生時に美しいトレースバックを表示
                show_path=False,  # ログ出力元のファイルパスを非表示に
                markup=True,  # [bold] のようなマークアップを有効にする
            )
        ],
    )