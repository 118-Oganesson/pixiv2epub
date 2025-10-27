# FILE: src/pixiv2epub/entrypoints/gui/manager.py
from pathlib import Path

from loguru import logger
from playwright.sync_api import Page

from ...app import Application
from ...domain.orchestrator import DownloadBuildOrchestrator
from ...infrastructure.builders.epub.builder import EpubBuilder
from ...shared.enums import GuiStatus
from ...shared.exceptions import Pixiv2EpubError
from ..provider_factory import ProviderFactory


class GuiManager:
    """GUIモードのバックエンドロジックを管理し、Playwrightページと連携します。"""

    def __init__(self, page: Page, app: Application):
        self.page = page
        self.app = app
        self.provider_factory = ProviderFactory(app.settings)

    def _run_task_from_browser(self, url: str) -> dict:
        """ブラウザから呼び出されるラッパー関数。"""
        log = logger.bind(url=url)
        log.info('ブラウザからタスク実行リクエストを受け取りました。')
        try:
            builder = EpubBuilder(self.app.settings)
            orchestrator = DownloadBuildOrchestrator(
                builder=builder,
                settings=self.app.settings,
                provider_factory=self.provider_factory,
            )
            result_paths = orchestrator.run_from_input(url)

            message = f'{len(result_paths)}件のEPUB生成に成功しました。'
            log.bind(result_count=len(result_paths)).success('タスクが完了しました。')
            return {'status': GuiStatus.SUCCESS, 'message': message}

        except Pixiv2EpubError as e:
            log.bind(error=str(e)).error('GUIタスクの処理中にエラーが発生しました。')
            return {'status': GuiStatus.ERROR, 'message': str(e)}
        except Exception as e:
            log.bind(error=str(e)).error(
                'GUIタスクの処理中に予期せぬエラーが発生しました。', exc_info=True
            )
            return {
                'status': GuiStatus.ERROR,
                'message': f'予期せぬエラーが発生しました: {e}',
            }

    def setup_bridge(self) -> None:
        """Python関数をJavaScriptに公開し、UI注入スクリプトをページに登録します。"""
        try:
            self.page.expose_function('pixiv2epub_run', self._run_task_from_browser)

            injector_path = Path(__file__).parent / 'assets' / 'injector.js'
            if not injector_path.is_file():
                raise FileNotFoundError(
                    f'インジェクタースクリプトが見つかりません: {injector_path}'
                )

            self.page.add_init_script(path=str(injector_path))

            logger.info(
                'GUIブリッジとインジェクタースクリプトのセットアップが完了しました。'
            )
        except Exception as e:
            logger.bind(error=str(e)).error('GUIブリッジのセットアップに失敗しました。')
            raise
