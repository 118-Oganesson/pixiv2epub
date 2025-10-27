# FILE: src/pixiv2epub/__main__.py
"""
パッケージを 'python -m pixiv2epub' コマンドで実行可能にするための
エントリーポイントです。
"""

from .entrypoints.cli import run_app

if __name__ == '__main__':
    run_app()
