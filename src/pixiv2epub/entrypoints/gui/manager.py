# src/pixiv2epub/entrypoints/gui/manager.py
import json
from pathlib import Path
from typing import Any

from loguru import logger
from playwright.sync_api import Page

from ...services import ApplicationService
from ...shared.constants import (
    ASSET_NAMES,
    PATTERNS,
)
from ...shared.enums import GuiStatus
from ...shared.exceptions import Pixiv2EpubError


class GuiManager:
    """GUIモードのバックエンドロジックを管理し、Playwrightページと連携します。"""

    def __init__(self, page: Page, app_service: ApplicationService):
        self.page = page
        self.app_service = app_service

    def _run_task_from_browser(self, url: str) -> dict[str, Any]:
        """ブラウザから呼び出されるラッパー関数。"""
        log = logger.bind(url=url)
        log.info('ブラウザからタスク実行リクエストを受け取りました。')
        try:
            result_paths = self.app_service.run_from_input(url)

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
            # 1. Python関数をブラウザに公開
            self.page.expose_function('pixiv2epub_run', self._run_task_from_browser)

            # 2. パターン設定をJSONとしてシリアライズ
            provider_config_json = json.dumps(PATTERNS.to_js_provider_config())

            # 3. GuiStatus Enumの値をJSに渡す
            status_map_json = json.dumps(
                {'SUCCESS': GuiStatus.SUCCESS, 'ERROR': GuiStatus.ERROR}
            )

            # 4. [修正] add_script_tag の代わりに add_init_script を使用する
            # これにより、injector.js が実行される前に
            # window オブジェクトに設定が確実に存在するようになる
            config_script = f"""
            window.PIXIV2EPUB_PROVIDER_CONFIG = {provider_config_json};
            window.PIXIV2EPUB_STATUS_MAP = {status_map_json};
            """
            self.page.add_init_script(script=config_script)

            # 5. インジェクタースクリプト本体も add_init_script で登録
            # (これは 4. の後に実行されることが保証される)
            injector_path = (
                Path(__file__).parent / 'assets' / ASSET_NAMES.INJECTOR_SCRIPT
            )
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
