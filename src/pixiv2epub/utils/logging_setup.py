#
# -----------------------------------------------------------------------------
# src/pixiv2epub/utils/logging_setup.py
#
# アプリケーション全体で使用するロギング機能の設定を行います。
# richライブラリを統合し、開発者にとって可読性の高いログ出力を提供します。
# -----------------------------------------------------------------------------
import logging

from rich.logging import RichHandler


def setup_logging(level="INFO"):
    """richライブラリを用いて、見やすく色付けされたログ出力を設定します。

    この関数はアプリケーションの起動時に一度だけ呼び出すことを想定しています。
    呼び出し後、Python標準の `logging` モジュールを通じて行われるすべての
    ログ出力が `rich` によってフォーマットされるようになります。

    Args:
        level (str, optional): 出力するログの最低レベル。
            'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL' などが指定可能です。
            デフォルトは "INFO" で、一般的な運用に必要な情報のみ表示します。
    """
    logging.basicConfig(
        level=level,
        # richハンドラ側でフォーマットするため、ルートロガーはメッセージをそのまま渡します。
        format="%(message)s",
        # タイムスタンプはrichハンドラによって解釈され、表示されます。
        datefmt="[%X]",
        # 既存のハンドラをすべてクリアし、RichHandlerのみを使用するようにします。
        force=True,
        handlers=[
            RichHandler(
                # Trueに設定すると、例外発生時にrichの美しいトレースバックが表示されます。
                # これにより、エラーの原因究明が容易になります。
                rich_tracebacks=True,
                # ログメッセージに `[bold]` のようなBBCode風のマークアップを有効にします。
                # これにより、ログの特定部分を強調表示できます。
                markup=True,
                # ログ出力元のファイルパスを非表示にし、コンソール出力を簡潔に保ちます。
                show_path=False,
            )
        ],
    )
