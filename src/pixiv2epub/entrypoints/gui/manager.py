# FILE: src/pixiv2epub/entrypoints/gui/manager.py
from pathlib import Path

from loguru import logger
from playwright.sync_api import Page

from ...app import Application
from ...shared.exceptions import Pixiv2EpubError
from ...utils.url_parser import parse_input
from ..providers import ProviderFactory


class GuiManager:
    """GUIモードのバックエンドロジックを管理し、Playwrightページと連携します。"""

    def __init__(self, page: Page, app: Application):
        self.page = page
        self.app = app
        self.provider_factory = ProviderFactory(app.settings)

    async def _run_task_from_browser(self, url: str) -> dict:
        """ブラウザから呼び出される非同期ラッパー関数。"""
        logger.info(f"ブラウザからタスク実行リクエスト: {url}")
        try:
            provider_enum, content_type_enum, target_id = parse_input(url)

            logger.info(
                f"処理を開始します: Provider={provider_enum.name}, "
                f"Type={content_type_enum.name}, ID={target_id}"
            )

            # Factoryを使用して適切なProviderを生成
            provider = self.provider_factory.create(provider_enum)

            # 統一されたApplicationのメソッドを呼び出す
            result_paths = self.app.run_download_and_build(
                provider, content_type_enum, target_id
            )

            message = f"{len(result_paths)}件のEPUB生成に成功しました。"
            logger.success(f"タスク完了: {message}")
            return {"status": "success", "message": message}

        except Pixiv2EpubError as e:
            logger.error(f"GUIタスクの処理中にエラーが発生しました: {e}")
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.error(
                f"GUIタスクの処理中に予期せぬエラーが発生しました: {e}", exc_info=True
            )
            return {"status": "error", "message": f"予期せぬエラーが発生しました: {e}"}

    def setup_bridge(self):
        """Python関数をJavaScriptに公開し、UI注入スクリプトをページに登録します。"""
        try:
            # 'pixiv2epub_run'という名前でPythonのメソッドをwindowオブジェクトに公開
            self.page.expose_function("pixiv2epub_run", self._run_task_from_browser)

            injector_path = Path(__file__).parent / "assets" / "injector.js"
            if not injector_path.is_file():
                raise FileNotFoundError(
                    f"インジェクタースクリプトが見つかりません: {injector_path}"
                )

            # このスクリプトは、ページが遷移するたびに実行されます
            self.page.add_init_script(path=str(injector_path))

            logger.info(
                "GUIブリッジとインジェクタースクリプトのセットアップが完了しました。"
            )
        except Exception as e:
            logger.error(f"GUIブリッジのセットアップに失敗しました: {e}")
            raise
