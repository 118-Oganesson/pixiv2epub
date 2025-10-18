# FILE: src/pixiv2epub/entrypoints/cli.py
import asyncio
from pathlib import Path
from typing import Any, List, Literal, Optional, Tuple

import typer
from dotenv import find_dotenv, set_key
from loguru import logger
from loguru._logger import Logger as LoguruLogger  # 正しい Logger 型をインポート
from playwright.sync_api import sync_playwright
from typing_extensions import Annotated

from ..app import Application
from ..domain.interfaces import (
    ICreatorProvider,
    IMultiWorkProvider,
    IProvider,
    IWorkProvider,
)
from ..domain.orchestrator import DownloadBuildOrchestrator
from ..infrastructure.builders.epub.builder import EpubBuilder
from ..infrastructure.providers.fanbox.auth import get_fanbox_sessid
from ..infrastructure.providers.pixiv.auth import get_pixiv_refresh_token
from ..models.workspace import Workspace
from ..shared.constants import MANIFEST_FILE_NAME
from ..shared.enums import (
    ContentType,
    Provider as ProviderEnum,
)
from ..shared.exceptions import (
    AuthenticationError,
    Pixiv2EpubError,
    SettingsError,
)
from ..shared.settings import Settings
from ..utils.logging import setup_logging
from ..utils.url_parser import parse_content_identifier
from .gui.manager import GuiManager
from .provider_factory import ProviderFactory
from .constants import DEFAULT_ENV_FILENAME, DEFAULT_GUI_SESSION_PATH

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

    def initialize_settings(
        self,
        config_file: Optional[Path],
        log_level: str,
        require_auth: bool = True,
    ):
        """設定オブジェクトを初期化する。"""
        if self._settings is None:
            try:
                self._settings = Settings(
                    _config_file=config_file,
                    log_level=log_level,
                    require_auth=require_auth,
                )
                self.provider_factory = ProviderFactory(self._settings)
            except SettingsError as e:
                logger.bind(error=str(e)).error("❌ 設定エラーが発生しました。")
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

    if ctx.invoked_subcommand == "auth":
        ctx.obj.initialize_settings(config, log_level, require_auth=False)
    elif ctx.invoked_subcommand is not None:
        require_auth = ctx.invoked_subcommand != "build"
        ctx.obj.initialize_settings(config, log_level, require_auth=require_auth)


@app.command()
def auth(
    ctx: typer.Context,
    service: Annotated[
        Literal["pixiv", "fanbox"],
        typer.Argument(
            help="認証するサービスを選択します ('pixiv' または 'fanbox')。",
            case_sensitive=False,
        ),
    ] = "pixiv",
):
    """ブラウザで指定されたサービスにログインし、認証情報を保存します。"""
    session_path = Path(DEFAULT_GUI_SESSION_PATH)
    env_path_str = find_dotenv()
    env_path = Path(env_path_str) if env_path_str else Path(DEFAULT_ENV_FILENAME)
    if not env_path.exists():
        env_path.touch()

    logger.bind(session_path=str(session_path.resolve())).info(
        "GUI用のブラウザセッションを使用します。"
    )

    try:
        app_state: AppState = ctx.obj
        if service == "pixiv":
            logger.info("Pixiv認証を開始します...")
            refresh_token = get_pixiv_refresh_token(
                save_session_path=session_path,
                settings=app_state.settings.providers.pixiv,
            )
            set_key(
                str(env_path),
                "PIXIV2EPUB_PROVIDERS__PIXIV__REFRESH_TOKEN",
                refresh_token,
            )
            logger.bind(env_path=str(env_path.resolve())).success(
                "Pixiv認証成功！ リフレッシュトークンを保存しました。"
            )

        elif service == "fanbox":
            logger.info("FANBOX認証を開始します...")
            sessid = asyncio.run(get_fanbox_sessid(session_path))
            set_key(str(env_path), "PIXIV2EPUB_PROVIDERS__FANBOX__SESSID", sessid)
            logger.bind(env_path=str(env_path.resolve())).success(
                "FANBOX認証成功！ FANBOXSESSIDを保存しました。"
            )
    except AuthenticationError as e:
        logger.bind(error=str(e)).error("❌ 認証に失敗しました。")
        raise typer.Exit(code=1)


def _parse_input_and_create_provider(
    app_state: AppState, input_str: str
) -> Tuple[IProvider, ProviderEnum, ContentType, Any, LoguruLogger]:
    """入力文字列を解析し、対応するプロバイダを生成して返す。"""
    if not app_state.provider_factory:
        raise RuntimeError("ProviderFactoryが初期化されていません。")

    provider_enum, content_type_enum, target_id = parse_content_identifier(input_str)
    provider = app_state.provider_factory.create(provider_enum)
    log = logger.bind(
        provider=provider_enum.name,
        content_type=content_type_enum.name,
        target_id=target_id,
    )
    return provider, provider_enum, content_type_enum, target_id, log


def _handle_run(app_state: AppState, target_input: str):
    """ダウンロードとビルド処理を実行します。"""
    # 1. まずコンテキスト情報（IDやプロバイダ）をパースします
    try:
        provider, provider_enum, content_type_enum, target_id, _ = (
            _parse_input_and_create_provider(app_state, target_input)
        )
    except Exception as e:
        logger.error(f"入力の解析に失敗しました: {e}", exc_info=True)
        return

    # 2. 処理全体を with logger.contextualize で囲みます
    with logger.contextualize(
        provider=provider_enum.name,
        content_type=content_type_enum.name,
        target_id=str(target_id),
    ):
        logger.info("ダウンロードとビルド処理を開始")

        builder = EpubBuilder(settings=app_state.settings)
        orchestrator = DownloadBuildOrchestrator(provider, builder, app_state.settings)

        if content_type_enum == ContentType.WORK:
            orchestrator.process_work(target_id)
        elif content_type_enum == ContentType.SERIES:
            orchestrator.process_series(target_id)
        elif content_type_enum == ContentType.CREATOR:
            orchestrator.process_creator(target_id)

        logger.success("✅ すべての処理が完了しました。")


def _handle_download(app_state: AppState, target_input: str):
    """ダウンロード処理のみを実行します。"""
    # 1. コンテキスト情報をパース
    try:
        provider, provider_enum, content_type_enum, target_id, _ = (
            _parse_input_and_create_provider(app_state, target_input)
        )
    except Exception as e:
        logger.error(f"入力の解析に失敗しました: {e}", exc_info=True)
        return

    # 2. 処理全体を with logger.contextualize で囲む
    with logger.contextualize(
        provider=provider_enum.name,
        content_type=content_type_enum.name,
        target_id=str(target_id),
    ):
        logger.info("ダウンロード処理のみを開始")

        workspaces: List[Workspace] = []
        if content_type_enum == ContentType.WORK and isinstance(
            provider, IWorkProvider
        ):
            workspace = provider.get_work(target_id)
            if workspace:
                workspaces.append(workspace)
        elif content_type_enum == ContentType.SERIES and isinstance(
            provider, IMultiWorkProvider
        ):
            workspaces = provider.get_multiple_works(target_id)
        elif content_type_enum == ContentType.CREATOR and isinstance(
            provider, ICreatorProvider
        ):
            workspaces = provider.get_creator_works(target_id)
        else:
            raise TypeError(
                f"現在のProviderは {content_type_enum.name} のダウンロードをサポートしていません。"
            )


@app.command()
def run(
    ctx: typer.Context,
    target_input: Annotated[
        str,
        typer.Argument(
            help="Pixiv/Fanboxの作品・シリーズ・ユーザーのURLまたはID。",
            metavar="INPUT",
        ),
    ],
):
    """指定されたURLまたはIDの作品をダウンロードし、EPUBをビルドします。"""
    _handle_run(ctx.obj, target_input)


@app.command()
def download(
    ctx: typer.Context,
    target_input: Annotated[
        str,
        typer.Argument(
            help="Pixiv/Fanboxの作品・シリーズ・ユーザーのURLまたはID。",
            metavar="INPUT",
        ),
    ],
):
    """作品データをワークスペースにダウンロードするだけで終了します。"""
    _handle_download(ctx.obj, target_input)


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
    app_instance = app_state.app

    workspaces_to_build: List[Path] = []

    try:
        Workspace.from_path(workspace_path)
        workspaces_to_build.append(workspace_path)
    except ValueError:
        logger.bind(search_path=str(workspace_path)).info(
            "ビルド可能なワークスペースを再帰的に検索します..."
        )
        for manifest_path in workspace_path.rglob(MANIFEST_FILE_NAME):
            workspaces_to_build.append(manifest_path.parent)

    if not workspaces_to_build:
        logger.bind(search_path=str(workspace_path)).warning(
            "ビルド可能なワークスペースが見つかりませんでした。"
        )
        return

    total = len(workspaces_to_build)
    success_count = 0
    logger.bind(count=total).info("✅ ビルド対象ワークスペースが見つかりました。")

    builder = EpubBuilder(settings=app_state.settings)
    for i, path in enumerate(workspaces_to_build, 1):
        log = logger.bind(
            current=i, total=total, workspace_name=path.name, workspace_path=str(path)
        )
        log.info("--- ビルド処理を開始 ---")
        try:
            output_path = app_instance.build_from_workspace(path, builder=builder)
            log.bind(output_path=str(output_path)).success("ビルド成功")
            success_count += 1
        except Exception as e:
            log.bind(error=str(e)).error(
                "❌ ビルドに失敗しました。",
                exc_info=app_state.settings.log_level == "DEBUG",
            )
        logger.info("---")
    logger.bind(success_count=success_count, total=total).info(
        "✨ 全てのビルド処理が完了しました。"
    )


@app.command()
def gui(
    ctx: typer.Context,
    service: Annotated[
        Literal["pixiv", "fanbox"],
        typer.Argument(
            help="最初に開くサービスを選択します ('pixiv' または 'fanbox')。",
            case_sensitive=False,
        ),
    ] = "pixiv",
):
    """ブラウザを起動し、PixivやFanboxページ上で直接操作するGUIモードを開始します。"""
    app_state: AppState = ctx.obj
    app_instance = app_state.app

    session_path = Path(DEFAULT_GUI_SESSION_PATH)
    logger.bind(session_path=str(session_path.resolve())).info(
        "GUIセッションのデータを保存/読込します。"
    )
    if not session_path.exists():
        logger.info("初回起動時、またはセッションが切れた場合はログインが必要です。")

    # サービスに基づいて開始URLを決定
    if service == "fanbox":
        start_url = "https://www.fanbox.cc/"
        service_name = "Fanbox"
    else:
        start_url = "https://www.pixiv.net/"
        service_name = "Pixiv"

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
                logger.info(f"{service_name}トップページに移動します。")
                page.goto(start_url, wait_until="domcontentloaded")
            else:
                logger.info("既存のセッションを再利用します。")

            logger.info(
                "ブラウザセッション待機中... ウィンドウを閉じるとプログラムは終了します。"
            )
            # ユーザーがブラウザを閉じるまで無期限に待機
            context.wait_for_event("close", timeout=0)
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
        logger.bind(error=str(e)).error("❌ 認証エラーが発生しました。")
        logger.info(
            "'pixiv2epub auth <service>' コマンドを実行して再認証してください。"
        )
        raise typer.Exit(code=1)
    except Pixiv2EpubError as e:
        logger.bind(error=str(e)).error(
            "❌ 処理中にエラーが発生しました。", exc_info=True
        )
        raise typer.Exit(code=1)
