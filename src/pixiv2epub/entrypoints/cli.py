# FILE: src/pixiv2epub/entrypoints/cli.py

import asyncio
from pathlib import Path
from typing import List, Literal, Optional

import typer
from dotenv import find_dotenv, set_key
from loguru import logger
from playwright.sync_api import sync_playwright
from typing_extensions import Annotated

from ..app import Application
from ..infrastructure.providers.fanbox.auth import get_fanbox_sessid
from ..infrastructure.providers.pixiv.auth import get_pixiv_refresh_token
from ..shared.exceptions import (
    AuthenticationError,
    Pixiv2EpubError,
    SettingsError,
)
from ..shared.settings import Settings
from ..utils.logging import setup_logging
from ..utils.url_parser import parse_input
from .gui.manager import GuiManager
from .providers import ProviderFactory

app = typer.Typer(
    help="PixivやFanboxの作品をURLやIDで指定し、高品質なEPUB形式に変換するコマンドラインツールです。",
    rich_markup_mode="markdown",
)


class AppState:
    """サブコマンドに渡すための状態を保持するクラス"""

    def __init__(self):
        self._settings: Optional[Settings] = None
        self._app: Optional[Application] = None
        self.provider_factory: Optional[ProviderFactory] = None

    def initialize_settings(self, config_file: Optional[Path], log_level: str):
        """設定オブジェクトを初期化する。"""
        if self._settings is None:
            try:
                self._settings = Settings(_config_file=config_file, log_level=log_level)
                self.provider_factory = ProviderFactory(self._settings)
            except SettingsError as e:
                logger.error(f"❌ 設定エラー: {e}")
                logger.info(
                    "先に 'pixiv2epub auth <service>' コマンドを実行して認証を完了してください。"
                )
                raise typer.Exit(code=1)

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            raise RuntimeError("Settingsが初期化されていません。")
        return self._settings

    @property
    def app(self) -> Application:
        """Applicationインスタンスへのアクセス。初回アクセス時に生成される。"""
        if self._settings is None:
            raise RuntimeError("Settingsが初期化されていません。")
        if self._app is None:
            logger.debug("Applicationインスタンスを生成します。")
            self._app = Application(self._settings)
        return self._app


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
    log_file: Annotated[
        bool,
        typer.Option(
            "--log-file",
            help="ログをJSON形式でファイルに出力します。",
            show_default=False,
        ),
    ] = False,
):
    """
    Pixiv/Fanbox to EPUB Converter
    """
    log_level = "DEBUG" if verbose else "INFO"

    setup_logging(log_level, serialize_to_file=log_file)

    ctx.obj = AppState()

    # auth と gui 以外のコマンド実行時に設定を初期化
    if ctx.invoked_subcommand not in ("auth", "gui"):
        ctx.obj.initialize_settings(config, log_level)


@app.command()
def auth(
    service: Annotated[
        Literal["pixiv", "fanbox"],
        typer.Argument(
            help="認証するサービスを選択します ('pixiv' または 'fanbox')。",
            case_sensitive=False,
        ),
    ] = "pixiv",
):
    """ブラウザで指定されたサービスにログインし、認証情報を保存します。"""
    session_path = Path("./.gui_session")
    env_path_str = find_dotenv()
    env_path = Path(env_path_str) if env_path_str else Path(".env")
    if not env_path.exists():
        env_path.touch()

    logger.info(
        f"GUI用のブラウザセッションを '{session_path.resolve()}' で使用します。"
    )

    try:
        if service == "pixiv":
            logger.info("Pixiv認証を開始します...")
            refresh_token = get_pixiv_refresh_token(save_session_path=session_path)
            set_key(
                str(env_path),
                "PIXIV2EPUB_PROVIDERS__PIXIV__REFRESH_TOKEN",
                refresh_token,
            )
            logger.success(
                f"Pixiv認証成功！ リフレッシュトークンを '{env_path.resolve()}' に保存しました。"
            )
        elif service == "fanbox":
            logger.info("FANBOX認証を開始します...")
            sessid = asyncio.run(get_fanbox_sessid(session_path))
            set_key(str(env_path), "PIXIV2EPUB_PROVIDERS__FANBOX__SESSID", sessid)
            logger.success(
                f"FANBOX認証成功！ FANBOXSESSIDを '{env_path.resolve()}' に保存しました。"
            )
    except AuthenticationError as e:
        logger.error(f"❌ 認証に失敗しました: {e}")
        raise typer.Exit(code=1)


def _execute_command(
    app_state: AppState,
    input_str: str,
    mode: Literal["run", "download"],
):
    """CLIのrun/downloadコマンド共通実行ロジック"""
    app_instance = app_state.app
    if not app_state.provider_factory:
        raise RuntimeError("ProviderFactoryが初期化されていません。")

    provider_enum, content_type_enum, target_id = parse_input(input_str)
    provider = app_state.provider_factory.create(provider_enum)

    if mode == "run":
        logger.info("ダウンロードとビルド処理を実行します...")
        app_instance.run_download_and_build(provider, content_type_enum, target_id)
        logger.success("✅ すべての処理が完了しました。")
    elif mode == "download":
        logger.info("ダウンロード処理のみを実行します...")
        workspaces = app_instance.run_download_only(
            provider, content_type_enum, target_id
        )
        for ws in workspaces:
            logger.success(f"ダウンロードが完了しました: {ws.root_path}")


@app.command()
def run(
    ctx: typer.Context,
    input_url_or_id: Annotated[
        str,
        typer.Argument(
            help="Pixiv/Fanboxの作品・シリーズ・ユーザーのURLまたはID。",
            metavar="INPUT",
        ),
    ],
):
    """指定されたURLまたはIDの作品をダウンロードし、EPUBをビルドします。"""
    _execute_command(ctx.obj, input_url_or_id, "run")


@app.command()
def download(
    ctx: typer.Context,
    input_url_or_id: Annotated[
        str,
        typer.Argument(
            help="Pixiv/Fanboxの作品・シリーズ・ユーザーのURLまたはID。",
            metavar="INPUT",
        ),
    ],
):
    """作品データをワークスペースにダウンロードするだけで終了します。"""
    _execute_command(ctx.obj, input_url_or_id, "download")


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
    # buildコマンドはProviderを必要としないため、ここで初めて初期化
    if ctx.invoked_subcommand == "build":
        app_state.initialize_settings(ctx.params.get("config"), "INFO")

    app_instance = app_state.app

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
            output_path = app_instance.build_from_workspace(path)
            logger.success(f"ビルド成功: {output_path}")
            success_count += 1
        except Exception as e:
            logger.error(
                f"❌ '{path.name}' のビルドに失敗しました: {e}",
                exc_info=app_state.settings.log_level == "DEBUG",
            )
    logger.info("---")
    logger.info(f"✨ 全てのビルド処理が完了しました。成功: {success_count}/{total}")


@app.command()
def gui(
    ctx: typer.Context,
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
    """ブラウザを起動し、Pixivページ上で直接操作するGUIモードを開始します。"""
    app_state: AppState = ctx.obj
    app_state.initialize_settings(config, "INFO")
    app_instance = app_state.app

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
            gui_manager = GuiManager(page, app_instance)
            gui_manager.setup_bridge()

            if page.url == "about:blank":
                logger.info("Pixivトップページに移動します。")
                page.goto("https://www.pixiv.net/")
            else:
                logger.info("既存のセッションを再利用します。")

            logger.info(
                "ブラウザセッション待機中... ウィンドウを閉じるとプログラムは終了します。"
            )
            page.wait_for_close()
    finally:
        logger.info("GUIモードを終了します。")


@logger.catch(exclude=Pixiv2EpubError)
def run_app():
    """
    アプリケーション全体を@logger.catchでラップし、
    制御下の例外は個別処理、それ以外をLoguruに記録させるためのラッパー関数。
    """
    try:
        app()
    except AuthenticationError as e:
        logger.error(f"❌ 認証エラー: {e}")
        logger.info(
            "'pixiv2epub auth <service>' コマンドを実行して再認証してください。"
        )
        raise typer.Exit(code=1)
    except Pixiv2EpubError as e:
        logger.error(f"❌ 処理中にエラーが発生しました: {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    run_app()
