# src/pixiv2epub/cli.py

import argparse
import logging
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

from .app import Application
from .core.auth import get_pixiv_refresh_token
from .core.exceptions import AuthenticationError, SettingsError
from .core.settings import Settings
from .gui import GuiManager
from .utils.logging import setup_logging
from .utils.url_parser import parse_input

logger = logging.getLogger(__name__)


def handle_auth(args: argparse.Namespace):
    """'auth' サブコマンドを処理し、.envファイルとGUIセッションを作成します。"""
    session_path = Path("./.gui_session")
    logger.info(
        f"GUI用のブラウザセッションを '{session_path.resolve()}' に作成します。"
    )

    if session_path.exists():
        logger.warning(
            f"既存のGUIセッションを削除して上書きします: {session_path.resolve()}"
        )
        shutil.rmtree(session_path)

    logger.info("Pixiv認証を開始します...")
    try:
        refresh_token = get_pixiv_refresh_token(save_session_path=session_path)

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
        logger.info("✅ GUI用のログインセッションも保存されました。")

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
    """
    'build' サブコマンドを処理します。
    指定されたパスがディレクトリの場合、再帰的にビルド可能なワークスペースを探して処理します。
    """
    base_path = Path(args.workspace_path).resolve()
    workspaces_to_build = []

    if not base_path.exists():
        logger.error(f"❌ 指定されたパスが見つかりません: {base_path}")
        return

    # 指定されたパス自体がビルド可能なワークスペースかチェック
    if base_path.is_dir() and (base_path / "manifest.json").is_file():
        workspaces_to_build.append(base_path)
    # ディレクトリの場合、再帰的に探索
    elif base_path.is_dir():
        logger.info(
            f"'{base_path}' 内のビルド可能なワークスペースを再帰的に検索します..."
        )
        for manifest_path in base_path.rglob("manifest.json"):
            workspaces_to_build.append(manifest_path.parent)

    if not workspaces_to_build:
        logger.warning(
            f"指定されたパスにビルド可能なワークスペースが見つかりませんでした: {base_path}"
        )
        return

    total = len(workspaces_to_build)
    success_count = 0
    logger.info(f"✅ {total}件のビルド対象ワークスペースが見つかりました。")

    for i, workspace_path in enumerate(workspaces_to_build, 1):
        logger.info(f"--- ビルド処理 ({i}/{total}): {workspace_path.name} ---")
        try:
            output_path = app.build_from_workspace(workspace_path)
            logger.info(f"✅ ビルド成功: {output_path}")
            success_count += 1
        except Exception as e:
            logger.error(
                f"❌ '{workspace_path.name}' のビルドに失敗しました: {e}",
                exc_info=False,
            )

    logger.info("---")
    logger.info(f"✨ 全てのビルド処理が完了しました。成功: {success_count}/{total}")


def handle_gui(args: argparse.Namespace, app: Application):
    """'gui' サブコマンドを処理し、永続的なブラウザセッションを開始します。"""
    session_path = Path("./.gui_session")
    logger.info(
        f"GUIセッションのデータを '{session_path.resolve()}' に保存/読込します。"
    )
    if not session_path.exists():
        logger.info(
            "初回起動時、またはセッションが切れた場合はPixivへのログインが必要です。"
        )

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                session_path,
                headless=False,
            )

            if context.pages:
                page = context.pages[0]
            else:
                page = context.new_page()

            gui_manager = GuiManager(page, app)
            gui_manager.setup_bridge()

            if page.url == "about:blank":
                logger.info("Pixivトップページに移動します。")
                page.goto("https://www.pixiv.net/")
            else:
                logger.info("既存のセッションを再利用します。")

            logger.info(
                "ブラウザセッション待機中... ウィンドウを閉じるとプログラムは終了します。"
            )
            while not page.is_closed():
                try:
                    page.wait_for_timeout(1000)
                except Exception:
                    break

    except Exception as e:
        logger.error(
            f"💥 GUIセッション中に致命的なエラーが発生しました: {e}", exc_info=True
        )
    finally:
        logger.info("GUIモードを終了します。")


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

    parser_auth = subparsers.add_parser(
        "auth",
        help="ブラウザでPixivにログインし、認証トークンとGUIセッションを保存します。",
    )
    parser_auth.set_defaults(func=handle_auth)

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

    parser_gui = subparsers.add_parser(
        "gui",
        help="ブラウザを起動し、Pixivページ上で直接操作するGUIモードを開始します。",
    )
    parser_gui.set_defaults(func=handle_gui)

    args = parser.parse_args()

    setup_logging(args.log_level)

    if args.command == "auth":
        args.func(args)
        return

    try:
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
