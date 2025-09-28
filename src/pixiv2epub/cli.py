# src/pixiv2epub/cli.py

import argparse
import logging
from pathlib import Path

from .app import Application
from .core.auth import get_pixiv_refresh_token
from .core.exceptions import AuthenticationError, SettingsError
from .core.settings import Settings
from .utils.logging import setup_logging
from .utils.url_parser import parse_input

logger = logging.getLogger(__name__)


def handle_auth(args: argparse.Namespace):
    """'auth' サブコマンドを処理し、.envファイルを作成します。"""
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
            f"✅ 認証に成功しました！ リフレッシュトークンを '{env_path.resolve()}' に保存しました。"
        )

    except AuthenticationError as e:
        logger.error(f"❌ 認証に失敗しました: {e}")
        exit(1)
    except Exception as e:
        logger.error(
            f"💥 認証プロセス中に予期せぬエラーが発生しました: {e}", exc_info=True
        )
        exit(1)


def handle_run(args: argparse.Namespace, app: Application):
    """'run' サブコマンド（ダウンロードとビルド）を処理します。"""
    target_type, target_id = parse_input(args.input)
    logger.info("ダウンロードとビルド処理を実行します...")

    if target_type == "novel":
        app.run_novel(target_id)
    elif target_type == "series":
        app.run_series(target_id)
    elif target_type == "user":
        app.run_user_novels(target_id)

    logger.info("✅ 処理が完了しました。")


def handle_download(args: argparse.Namespace, app: Application):
    """'download' サブコマンドを処理します。"""
    target_type, target_id = parse_input(args.input)
    logger.info("ダウンロード処理のみを実行します...")

    if target_type == "novel":
        ws = app.download_novel(target_id)
        logger.info(f"✅ ダウンロードが完了しました: {ws.root_path}")
    elif target_type == "series":
        wss = app.download_series(target_id)
        logger.info(f"✅ {len(wss)}件のダウンロードが完了しました。")
    elif target_type == "user":
        wss = app.download_user_novels(target_id)
        logger.info(f"✅ {len(wss)}件のダウンロードが完了しました。")


def handle_build(args: argparse.Namespace, app: Application):
    """'build' サブコマンドを処理します。"""
    workspace_path = Path(args.workspace_path)
    logger.info(f"ビルド処理を実行します: {workspace_path}")
    output_path = app.build_from_workspace(workspace_path)
    logger.info(f"✅ ビルドが完了しました: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Pixivから小説をダウンロードし、EPUB形式に変換します。",
        prog="pixiv2epub",
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

    subparsers = parser.add_subparsers(dest="command", help="実行するコマンド")
    subparsers.required = True

    # 'auth' コマンド
    parser_auth = subparsers.add_parser(
        "auth",
        help="ブラウザでPixivにログインし、認証トークンを.envファイルに保存します。",
    )
    parser_auth.set_defaults(func=handle_auth)

    # 'run' コマンド
    parser_run = subparsers.add_parser(
        "run",
        help="指定されたURLまたはIDの小説をダウンロードし、EPUBをビルドします。",
    )
    parser_run.add_argument(
        "input", help="Pixivの小説・シリーズ・ユーザーのURLまたはID。"
    )
    parser_run.add_argument(
        "-c", "--config", type=str, help="カスタム設定TOMLファイルへのパス。"
    )
    parser_run.set_defaults(func=handle_run)

    # 'download' コマンド
    parser_download = subparsers.add_parser(
        "download",
        help="小説データをワークスペースにダウンロードするだけで終了します。",
    )
    parser_download.add_argument(
        "input", help="Pixivの小説・シリーズ・ユーザーのURLまたはID。"
    )
    parser_download.add_argument(
        "-c", "--config", type=str, help="カスタム設定TOMLファイルへのパス。"
    )
    parser_download.set_defaults(func=handle_download)

    # 'build' コマンド
    parser_build = subparsers.add_parser(
        "build",
        help="既存のワークスペースディレクトリからEPUBをビルドします。",
    )
    parser_build.add_argument(
        "workspace_path",
        metavar="WORKSPACE_PATH",
        type=Path,
        help="ビルド対象のワークスペースディレクトリへのパス。",
    )
    parser_build.add_argument(
        "-c", "--config", type=str, help="カスタム設定TOMLファイルへのパス。"
    )
    parser_build.set_defaults(func=handle_build)

    args = parser.parse_args()

    setup_logging(args.log_level)

    # `auth`コマンドはSettingsを必要としないため、先に処理
    if args.command == "auth":
        args.func(args)
        return

    try:
        # 他のコマンドはSettingsの初期化が必要
        config_path = getattr(args, "config", None)
        settings = Settings(_config_file=config_path, log_level=args.log_level)
        app = Application(settings)
        args.func(args, app)
    except SettingsError as e:
        logger.error(f"❌ 設定エラー: {e}")
        logger.info("先に 'pixiv2epub auth' コマンドを実行して認証を完了してください。")
        exit(1)
    except Exception as e:
        logger.error(f"💥 処理中にエラーが発生しました: {e}", exc_info=True)
        exit(1)


if __name__ == "__main__":
    main()
