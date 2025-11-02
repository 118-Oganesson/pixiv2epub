# FILE: src/pixiv2epub/entrypoints/cli.py
import asyncio
from pathlib import Path
from typing import Annotated

import typer
from dotenv import find_dotenv, set_key
from loguru import logger
from playwright.sync_api import sync_playwright
from pybreaker import CircuitBreaker

from ..domain.interfaces import IProvider
from ..infrastructure.builders.epub.builder import EpubBuilder
from ..infrastructure.providers.fanbox.auth import get_fanbox_sessid
from ..infrastructure.providers.fanbox.client import FanboxApiClient
from ..infrastructure.providers.fanbox.provider import FanboxProvider
from ..infrastructure.providers.pixiv.auth import get_pixiv_refresh_token
from ..infrastructure.providers.pixiv.client import PixivApiClient
from ..infrastructure.providers.pixiv.provider import PixivProvider
from ..infrastructure.repositories.filesystem import FileSystemWorkspaceRepository
from ..services import ApplicationService
from ..shared.enums import Provider as ProviderEnum
from ..shared.exceptions import (
    AuthenticationError,
    Pixiv2EpubError,
    SettingsError,
)
from ..shared.settings import Settings
from ..utils.logging import setup_logging
from .gui.manager import GuiManager

app = typer.Typer(
    help='PixivやFanboxの作品をURLやIDで指定し、高品質なEPUB形式に変換するコマンドラインツールです。',
    rich_markup_mode='markdown',
)


def _initialize_settings(
    config_file: Path | None,
    log_level: str,
    require_auth: bool = True,
) -> Settings:
    """設定オブジェクトを初期化するヘルパー関数。"""
    try:
        settings = Settings(
            _config_file=config_file,
            log_level=log_level,
            require_auth=require_auth,
        )
        return settings
    except SettingsError as e:
        logger.bind(error=str(e)).error('❌ 設定エラーが発生しました。')
        logger.info(
            "先に 'pixiv2epub auth <service>' コマンドを実行して認証を完了してください。"
        )
        raise typer.Exit(code=1) from e


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    verbose: Annotated[
        bool,
        typer.Option(
            '-v',
            '--verbose',
            help='詳細なデバッグログを有効にします。',
            show_default=False,
        ),
    ] = False,
    config: Annotated[
        Path | None,
        typer.Option(
            '-c',
            '--config',
            help='カスタム設定TOMLファイルへのパス。',
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
            '--log-file',
            help='ログをJSON形式でファイルに出力します。',
            show_default=False,
        ),
    ] = False,
) -> None:
    """
    Pixiv/Fanbox to EPUB Converter
    """
    log_level = 'DEBUG' if verbose else 'INFO'
    setup_logging(log_level, serialize_to_file=log_file)

    # 'auth' コマンドの場合は、認証情報を必要としない設定のみ初期化
    if ctx.invoked_subcommand == 'auth':
        settings = _initialize_settings(config, log_level, require_auth=False)
        # auth コマンドは ApplicationService を必要としないため、
        # Settings のみをコンテキストに渡す (auth ハンドラが利用)
        ctx.obj = settings
        return

    # 'auth' 以外のコマンドが呼び出された場合 (またはコマンドなし)、
    # 完全な依存関係の構築を試みる
    if ctx.invoked_subcommand is not None:
        # 1. 設定の初期化 (認証必須)
        # 'build' コマンドは認証を必要としない
        require_auth = ctx.invoked_subcommand != 'build'
        settings = _initialize_settings(config, log_level, require_auth=require_auth)

        # 2. 共有リソースの構築
        shared_breaker = CircuitBreaker(
            fail_max=settings.downloader.circuit_breaker.fail_max,
            reset_timeout=settings.downloader.circuit_breaker.reset_timeout,
        )
        repository = FileSystemWorkspaceRepository(settings.workspace)
        builder = EpubBuilder(settings=settings)

        # 3. プロバイダーの構築
        providers: dict[ProviderEnum, IProvider] = {}

        # Pixiv (認証情報が利用可能な場合のみ構築)
        if settings.providers.pixiv.refresh_token:
            try:
                pixiv_api_client = PixivApiClient(
                    breaker=shared_breaker,
                    provider_name=PixivProvider.get_provider_name(),
                    auth_settings=settings.providers.pixiv,
                    api_delay=settings.downloader.api_delay,
                    api_retries=settings.downloader.api_retries,
                )
                providers[ProviderEnum.PIXIV] = PixivProvider(
                    settings=settings,
                    api_client=pixiv_api_client,
                    repository=repository,
                )
            except Exception as e:
                logger.warning(f'Pixivプロバイダーの初期化に失敗しました: {e}')

        # Fanbox (認証情報が利用可能な場合のみ構築)
        if settings.providers.fanbox.sessid:
            try:
                fanbox_api_client = FanboxApiClient(
                    breaker=shared_breaker,
                    provider_name=FanboxProvider.get_provider_name(),
                    auth_settings=settings.providers.fanbox,
                    api_delay=settings.downloader.api_delay,
                    api_retries=settings.downloader.api_retries,
                )
                providers[ProviderEnum.FANBOX] = FanboxProvider(
                    settings=settings,
                    api_client=fanbox_api_client,
                    repository=repository,
                )
            except Exception as e:
                logger.warning(f'Fanboxプロバイダーの初期化に失敗しました: {e}')

        # 4. ApplicationService の構築
        app_service = ApplicationService(
            settings=settings,
            builder=builder,
            repository=repository,
            providers=providers,
        )

        # 5. 完成したサービスをコンテキストに設定
        ctx.obj = app_service


@app.command()
def auth(
    ctx: typer.Context,
    service: Annotated[
        str,
        typer.Argument(
            help="認証するサービスを選択します ('pixiv' または 'fanbox')。",
            case_sensitive=False,
        ),
    ] = 'pixiv',
) -> None:
    """ブラウザで指定されたサービスにログインし、認証情報を保存します。"""

    settings: Settings = ctx.obj
    session_path = Path(settings.cli.default_gui_session_path)
    env_path_str = find_dotenv()
    env_path = (
        Path(env_path_str) if env_path_str else Path(settings.cli.default_env_filename)
    )

    if not env_path.exists():
        env_path.touch()

    logger.bind(session_path=str(session_path.resolve())).info(
        'GUI用のブラウザセッションを使用します。'
    )

    try:
        if service == 'pixiv':
            logger.info('Pixiv認証を開始します...')
            refresh_token = get_pixiv_refresh_token(
                save_session_path=session_path,
                settings=settings.providers.pixiv,
            )
            set_key(
                str(env_path),
                'PIXIV2EPUB_PROVIDERS__PIXIV__REFRESH_TOKEN',
                refresh_token,
            )
            logger.bind(env_path=str(env_path.resolve())).success(
                'Pixiv認証成功! リフレッシュトークンを保存しました。'
            )
        elif service == 'fanbox':
            logger.info('FANBOX認証を開始します...')
            sessid = asyncio.run(get_fanbox_sessid(session_path))
            set_key(str(env_path), 'PIXIV2EPUB_PROVIDERS__FANBOX__SESSID', sessid)
            logger.bind(env_path=str(env_path.resolve())).success(
                'FANBOX認証成功! FANBOXSESSIDを保存しました。'
            )
    except AuthenticationError as e:
        logger.bind(error=str(e)).error('❌ 認証に失敗しました。')
        raise typer.Exit(code=1) from e


@app.command()
def run(
    ctx: typer.Context,
    target_input: Annotated[
        str,
        typer.Argument(
            help='Pixiv/Fanboxの作品・シリーズ・ユーザーのURLまたはID。',
            metavar='INPUT',
        ),
    ],
) -> None:
    """指定されたURLまたはIDの作品をダウンロードし、EPUBをビルドします。"""
    app_service: ApplicationService = ctx.obj
    try:
        app_service.run_from_input(target_input)
        logger.success('✅ すべての処理が完了しました。')
    except Exception as e:
        logger.error(f'処理中にエラーが発生しました: {e}', exc_info=True)


@app.command()
def download(
    ctx: typer.Context,
    target_input: Annotated[
        str,
        typer.Argument(
            help='Pixiv/Fanboxの作品・シリーズ・ユーザーのURLまたはID。',
            metavar='INPUT',
        ),
    ],
) -> None:
    """作品データをワークスペースにダウンロードするだけで終了します。"""
    app_service: ApplicationService = ctx.obj
    try:
        app_service.download_from_input(target_input)
    except Exception as e:
        logger.error(f'ダウンロード処理中にエラーが発生しました: {e}', exc_info=True)


@app.command()
def build(
    ctx: typer.Context,
    workspace_path: Annotated[
        Path,
        typer.Argument(
            help='ビルド対象のワークスペースディレクトリ(またはその親)へのパス。',
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            metavar='WORKSPACE_PATH',
        ),
    ],
) -> None:
    """既存のワークスペースディレクトリからEPUBをビルドします。"""
    app_service: ApplicationService = ctx.obj
    app_service.build_from_workspaces(workspace_path)


@app.command()
def gui(
    ctx: typer.Context,
    service: Annotated[
        str,
        typer.Argument(
            help="最初に開くサービスを選択します ('pixiv' または 'fanbox')。",
            case_sensitive=False,
        ),
    ] = 'pixiv',
) -> None:
    """ブラウザを起動し、PixivやFanboxページ上で直接操作するGUIモードを開始します。"""
    app_service: ApplicationService = ctx.obj
    settings = app_service.settings  # サービスから設定を取得

    session_path = Path(settings.cli.default_gui_session_path)

    logger.bind(session_path=str(session_path.resolve())).info(
        'GUIセッションのデータを保存/読込します。'
    )
    if not session_path.exists():
        logger.info('初回起動時、またはセッションが切れた場合はログインが必要です。')

    # サービスに基づいて開始URLを決定
    if service == 'fanbox':
        start_url = 'https://www.fanbox.cc/'
        service_name = 'Fanbox'
    else:
        start_url = 'https://www.pixiv.net/'
        service_name = 'Pixiv'

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                session_path,
                headless=False,
            )
            page = context.pages[0] if context.pages else context.new_page()

            gui_manager = GuiManager(page, app_service)
            gui_manager.setup_bridge()

            if page.url == 'about:blank':
                logger.info(f'{service_name}トップページに移動します。')
                page.goto(start_url, wait_until='domcontentloaded')
            else:
                logger.info('既存のセッションを再利用します。')

            logger.info(
                'ブラウザセッション待機中... ウィンドウを閉じるとプログラムは終了します。'
            )
            # ユーザーがブラウザを閉じるまで無期限に待機
            context.wait_for_event('close', timeout=0)
    finally:
        logger.info('GUIモードを終了します。')


@logger.catch(exclude=Pixiv2EpubError)
def run_app() -> None:
    """
    アプリケーション全体を@logger.catchでラップし、
    制御下の例外は個別処理、それ以外をLoguruに記録させるためのラッパー関数。
    """
    try:
        app()
    except AuthenticationError as e:
        logger.bind(error=str(e)).error('❌ 認証エラーが発生しました。')
        logger.info(
            "'pixiv2epub auth <service>' コマンドを実行して再認証してください。"
        )
        raise typer.Exit(code=1) from e
    except Pixiv2EpubError as e:
        logger.bind(error=str(e)).error(
            '❌ 処理中にエラーが発生しました。', exc_info=True
        )
        raise typer.Exit(code=1) from e
