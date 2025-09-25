# src/pixiv2epub/utils/logging.py

import logging
from rich.logging import RichHandler


def setup_logging(level="INFO"):
    """
    richライブラリを用いて、見やすく色付けされたログ出力を設定します。

    Args:
        level (str, optional): 出力するログの最低レベル。 Defaults to "INFO".
    """
    logging.basicConfig(
        level=level.upper(),
        format="%(message)s",
        datefmt="[%X]",
        force=True,
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                markup=True,
                show_path=False,
            )
        ],
    )
