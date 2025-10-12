# FILE: src/pixiv2epub/entrypoints/cli.py
import shutil
from pathlib import Path
from typing import List, Optional

import typer
from loguru import logger
from playwright.sync_api import sync_playwright
from typing_extensions import Annotated

from ..app import Application
from ..infrastructure.providers.pixiv.auth import get_pixiv_refresh_token
from ..shared.exceptions import AuthenticationError, SettingsError
from ..shared.settings import Settings
from ..utils.logging import setup_logging
from ..utils.url_parser import parse_input
from .gui.manager import GuiManager

app = typer.Typer(
    help="Pixivの小説をURLやIDで指定し、高品質なEPUB形式に変換するコマンドラインツールです。",
    rich_markup_mode="markdown",
)


class AppState:
    """サブコマンドに渡すための状態を保持するクラス"""

    def __init__(self, app_instance: Optional[Application] = None):
        self.app = app_instance


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    verbose: Annotated[
        bool,
        typer.Option(
            "-v",
            "--verbose",
            help="詳細なデバッグログを有効にします。",
            show_default=False,
        ),
    ] = False,
    config: Annotated[
        Optional[Path],
        typer.Option(
            "-c",
            "--config",
            help="カスタム設定TOMLファイルへのパス。",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ] = None,
):
    """
    Pixiv to EPUB Converter
    """
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(log_level)

    if ctx.invoked_subcommand == "auth":
        ctx.obj = AppState()
        return

    try:
        settings = Settings(_config_file=config, log_level=log_level)
        app_instance = Application(settings)
        ctx.obj = AppState(app_instance=app_instance)
    except SettingsError as e:
        logger.error(f"❌ 設定エラー: {e}")
        logger.info("先に 'pixiv2epub auth' コマンドを実行して認証を完了してください。")
        raise typer.Exit(code=1)


@app.command()
def auth():
    """ブラウザでPixivにログインし、認証トークンとGUIセッションを保存します。"""
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
            typer.confirm(
                "'.env' ファイルは既に存在します。上書きしますか？", abort=True
            )

        env_path.write_text(env_content, encoding="utf-8")
        logger.info(
            f"✅ 認証に成功しました！ リフレッシュトークンを '{env_path.resolve()}' に保存しました。"
        )
        logger.info("✅ GUI用のログインセッションも保存されました。")

    except typer.Abort:
        logger.info("操作を中断しました。")
    except AuthenticationError as e:
        logger.error(f"❌ 認証に失敗しました: {e}")
        raise typer.Exit(code=1)


@app.command()
def run(
    ctx: typer.Context,
    input_url_or_id: Annotated[
        str,
        typer.Argument(
            help="Pixivの小説・シリーズ・ユーザーのURLまたはID。", metavar="INPUT"
        ),
    ],
):
    """指定されたURLまたはIDの小説をダウンロードし、EPUBをビルドします。"""
    app_state: AppState = ctx.obj
    if not app_state.app:
        logger.error("Applicationインスタンスが初期化されていません。")
        raise typer.Exit(code=1)

    target_type, target_id = parse_input(input_url_or_id)
    logger.info("ダウンロードとビルド処理を実行します...")

    if target_type == "novel":
        app_state.app.process_novel_to_epub(target_id)
    elif target_type == "series":
        app_state.app.process_series_to_epub(target_id)
    elif target_type == "user":
        app_state.app.process_user_novels_to_epub(target_id)

    logger.info("✅ 処理が完了しました。")


@app.command()
def download(
    ctx: typer.Context,
    input_url_or_id: Annotated[
        str,
        typer.Argument(
            help="Pixivの小説・シリーズ・ユーザーのURLまたはID。", metavar="INPUT"
        ),
    ],
):
    """小説データをワークスペースにダウンロードするだけで終了します。"""
    app_state: AppState = ctx.obj
    if not app_state.app:
        logger.error("Applicationインスタンスが初期化されていません。")
        raise typer.Exit(code=1)

    target_type, target_id = parse_input(input_url_or_id)
    logger.info("ダウンロード処理のみを実行します...")

    if target_type == "novel":
        ws = app_state.app.download_novel(target_id)
        logger.info(f"✅ ダウンロードが完了しました: {ws.root_path}")
    elif target_type == "series":
        wss = app_state.app.download_series(target_id)
        logger.info(f"✅ {len(wss)}件のダウンロードが完了しました。")
    elif target_type == "user":
        wss = app_state.app.download_user_novels(target_id)
        logger.info(f"✅ {len(wss)}件のダウンロードが完了しました。")


@app.command()
def build(
    ctx: typer.Context,
    workspace_path: Annotated[
        Path,
        typer.Argument(
            help="ビルド対象のワークスペースディレクトリへのパス。",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            metavar="WORKSPACE_PATH",
        ),
    ],
):
    """既存のワークスペースディレクトリからEPUBをビルドします。"""
    app_state: AppState = ctx.obj
    if not app_state.app:
        logger.error("Applicationインスタンスが初期化されていません。")
        raise typer.Exit(code=1)

    workspaces_to_build: List[Path] = []

    if (workspace_path / "manifest.json").is_file():
        workspaces_to_build.append(workspace_path)
    else:
        logger.info(
            f"'{workspace_path}' 内のビルド可能なワークスペースを再帰的に検索します..."
        )
        for manifest_path in workspace_path.rglob("manifest.json"):
            workspaces_to_build.append(manifest_path.parent)

    if not workspaces_to_build:
        logger.warning(
            f"指定されたパスにビルド可能なワークスペースが見つかりませんでした: {workspace_path}"
        )
        return

    total = len(workspaces_to_build)
    success_count = 0
    logger.info(f"✅ {total}件のビルド対象ワークスペースが見つかりました。")

    for i, path in enumerate(workspaces_to_build, 1):
        logger.info(f"--- ビルド処理 ({i}/{total}): {path.name} ---")
        try:
            output_path = app_state.app.build_from_workspace(path)
            logger.info(f"✅ ビルド成功: {output_path}")
            success_count += 1
        except Exception as e:
            logger.error(f"❌ '{path.name}' のビルドに失敗しました: {e}")

    logger.info("---")
    logger.info(f"✨ 全てのビルド処理が完了しました。成功: {success_count}/{total}")


@app.command()
def gui(ctx: typer.Context):
    """ブラウザを起動し、Pixivページ上で直接操作するGUIモードを開始します。"""
    app_state: AppState = ctx.obj
    if not app_state.app:
        logger.error("Applicationインスタンスが初期化されていません。")
        raise typer.Exit(code=1)

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
            page = context.pages[0] if context.pages else context.new_page()
            gui_manager = GuiManager(page, app_state.app)
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
    finally:
        logger.info("GUIモードを終了します。")


@logger.catch
def run_app():
    """
    アプリケーション全体を@logger.catchでラップし、
    未捕捉の例外をすべてLoguruに記録させるためのラッパー関数。
    """
    app()


if __name__ == "__main__":
    run_app()
