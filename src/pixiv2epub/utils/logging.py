# FILE: src/pixiv2epub/utils/logging.py
from loguru import logger
from rich.logging import RichHandler


def setup_logging(level: str = "INFO"):
    """
    LoguruをRichHandlerを使用するように設定します。
    Loguruのフォーマットを無効にし、RichHandlerに全てのフォーマットを委任します。
    """
    logger.remove()  # デフォルトハンドラの削除
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
    logger.info(f"ログレベルを {level.upper()} に設定しました。")
