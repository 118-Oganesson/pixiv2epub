# src/pixiv2epub/cli.py

import argparse
import logging
from pathlib import Path

from .app import Application
from .core.settings import Settings
from .utils.url_parser import parse_input


def main():
    parser = argparse.ArgumentParser(
        description="Pixivから小説をダウンロードし、EPUB形式に変換します。"
    )
    parser.add_argument("input", help="Pixivの小説・シリーズ・ユーザーのURLまたはID。")
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="小説データをワークスペースにダウンロードするだけで終了します。",
    )
    parser.add_argument(
        "--build-only",
        metavar="WORKSPACE_PATH",
        type=Path,
        help="既存のワークスペースディレクトリからEPUBをビルドするだけで終了します。",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        help="カスタム設定TOMLファイルへのパス。",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_const",
        dest="log_level",
        const="DEBUG",
        default="INFO",
        help="詳細なデバッグログを有効にします。",
    )
    args = parser.parse_args()
    logger = logging.getLogger(__name__)

    try:
        # 1. 設定とアプリケーションを一度だけ初期化
        settings = Settings(_config_file=args.config, log_level=args.log_level)
        app = Application(settings)

        # 2. モードに応じて処理を分岐
        if args.build_only:
            logger.info(f"ビルド処理を実行します: {args.build_only}")
            output_path = app.build_from_workspace(args.build_only)
            logger.info(f"ビルドが完了しました: {output_path}")
            return

        target_type, target_id = parse_input(args.input)

        if args.download_only:
            logger.info("ダウンロード処理のみを実行します...")
            if target_type == "novel":
                ws = app.download_novel(target_id)
                logger.info(f"ダウンロードが完了しました: {ws.root_path}")
            elif target_type == "series":
                wss = app.download_series(target_id)
                logger.info(f"{len(wss)}件のダウンロードが完了しました。")
            elif target_type == "user":
                wss = app.download_user_novels(target_id)
                logger.info(f"{len(wss)}件のダウンロードが完了しました。")
            return

        # 通常実行
        logger.info("ダウンロードとビルド処理を実行します...")
        if target_type == "novel":
            app.run_novel(target_id)
        elif target_type == "series":
            app.run_series(target_id)
        elif target_type == "user":
            app.run_user_novels(target_id)

    except Exception as e:
        # エラーログはrichによって自動的に整形される
        logger.error(f"処理中にエラーが発生しました: {e}", exc_info=True)
        exit(1)


if __name__ == "__main__":
    main()
