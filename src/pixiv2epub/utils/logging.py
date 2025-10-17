# FILE: src/pixiv2epub/utils/logging.py
from loguru import logger
from rich.logging import RichHandler


def setup_logging(level: str = "INFO", serialize_to_file: bool = False):
    """
    LoguruをRichHandlerとJSONファイル出力用に設定します。
    """
    logger.remove()  # デフォルトハンドラの削除

    # コンソール用のハンドラ
    logger.add(
        RichHandler(
            rich_tracebacks=True,
            show_path=False,
            markup=True,
            log_time_format="[%X]",  # RichHandlerに時刻フォーマットを指定
        ),
        level=level.upper(),
        format="{message}",  # RichHandlerにフォーマットを完全に委任
        backtrace=False,
        diagnose=False,
    )

    # ファイル出力用のハンドラ (JSON形式)
    if serialize_to_file:
        logger.add(
            "logs/pixiv2epub_{time}.log",  # ログファイルパス
            level="DEBUG",  # ファイルにはより詳細な情報を記録
            serialize=True,  # この設定がログをJSON形式にする
            enqueue=True,  # ログ出力を非同期にし、アプリケーションのパフォーマンスへの影響を最小化
            rotation="10 MB",  # 10MBでファイルをローテーション
            retention="7 days",  # 7日間ログを保持
            backtrace=True,
            diagnose=True,
        )

    logger.info(
        "ロガーが設定されました。レベル: {}, ファイル出力: {}",
        level.upper(),
        serialize_to_file,
    )
