# src/pixiv2epub/cli.py

import argparse
import logging
from pathlib import Path

from .core.auth import get_pixiv_refresh_token
from .core.exceptions import AuthenticationError
from .app import Application
from .core.settings import Settings, SettingsError
from .utils.url_parser import parse_input
from .utils.logging import setup_logging

logger = logging.getLogger(__name__)


def handle_auth(args):
    """'auth' サブコマンドを処理し、.envファイルを作成する。"""
    logger.info("Pixiv認証を開始します...")
    try:
        refresh_token = get_pixiv_refresh_token()

        env_path = Path(".env")
        env_content = f'PIXIV2EPUB_AUTH__REFRESH_TOKEN="{refresh_token}"'

        if env_path.exists():
            overwrite = input(
                "'.env' ファイルは既に存在します。上書きしますか？ (y/N): "
            ).lower()
            if overwrite != "y":
                logger.info("操作を中断しました。")
                return

        env_path.write_text(env_content, encoding="utf-8")
        logger.info(
            f"認証に成功しました！ リフレッシュトークンを '{env_path.resolve()}' に保存しました。"
        )

    except AuthenticationError as e:
        logger.error(f"認証に失敗しました: {e}")
        exit(1)
    except Exception as e:
        logger.error(
            f"認証プロセス中に予期せぬエラーが発生しました: {e}", exc_info=True
        )
        exit(1)


def handle_run(args):
    """'run' サブコマンド（URLやIDの処理）を処理する。"""
    try:
        settings = Settings(_config_file=args.config, log_level=args.log_level)
        app = Application(settings)

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

        logger.info("ダウンロードとビルド処理を実行します...")
        if target_type == "novel":
            app.run_novel(target_id)
        elif target_type == "series":
            app.run_series(target_id)
        elif target_type == "user":
            app.run_user_novels(target_id)

    except SettingsError as e:
        logger.error(f"設定エラー: {e}")
        logger.info(
            "先に 'python -m pixiv2epub auth' コマンドを実行して認証を完了してください。"
        )
        exit(1)
    except Exception as e:
        logger.error(f"処理中にエラーが発生しました: {e}", exc_info=True)
        exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Pixivから小説をダウンロードし、EPUB形式に変換します。"
    )

    subparsers = parser.add_subparsers(
        dest="command", required=True, help="実行するコマンド"
    )

    parser_auth = subparsers.add_parser(
        "auth",
        help="ブラウザでPixivにログインし、認証トークンを取得して .env ファイルを作成します。",
    )
    parser_auth.set_defaults(func=handle_auth)

    parser_run = subparsers.add_parser(
        "run", help="指定されたURLまたはIDの小説をダウンロード・ビルドします。"
    )
    parser_run.add_argument(
        "input", help="Pixivの小説・シリーズ・ユーザーのURLまたはID。"
    )
    parser_run.add_argument(
        "--download-only",
        action="store_true",
        help="小説データをワークスペースにダウンロードするだけで終了します。",
    )
    parser_run.add_argument(
        "--build-only",
        metavar="WORKSPACE_PATH",
        type=Path,
        help="既存のワークスペースディレクトリからEPUBをビルドするだけで終了します。",
    )
    parser_run.add_argument(
        "-c",
        "--config",
        type=str,
        help="カスタム設定TOMLファイルへのパス。",
    )
    parser_run.add_argument(
        "-v",
        "--verbose",
        action="store_const",
        dest="log_level",
        const="DEBUG",
        default="INFO",
        help="詳細なデバッグログを有効にします。",
    )
    parser_run.set_defaults(func=handle_run)

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

    log_level = getattr(args, "log_level", "INFO")
    setup_logging(log_level)

    if hasattr(args, "func"):
        args.func(args)
    else:
        args.input = args.command
        args.command = "run"
        handle_run(args)


if __name__ == "__main__":
    main()
