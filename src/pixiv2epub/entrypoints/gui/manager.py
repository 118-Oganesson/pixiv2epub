# FILE: src/pixiv2epub/entrypoints/gui/manager.py
from pathlib import Path
from typing import List

from loguru import logger
from playwright.sync_api import Page

from ...app import Application
from ...domain.orchestrator import DownloadBuildOrchestrator
from ...infrastructure.builders.epub.builder import EpubBuilder
from ...shared.enums import ContentType, GuiStatus
from ...shared.exceptions import Pixiv2EpubError
from ...utils.url_parser import parse_content_identifier

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
        log.info("ブラウザからタスク実行リクエストを受け取りました。")
        try:
            provider_enum, content_type_enum, target_id = parse_content_identifier(url)

            log.bind(
                provider=provider_enum.name,
                content_type=content_type_enum.name,
                target_id=target_id,
            ).info("処理を開始します。")

            provider = self.provider_factory.create(provider_enum)
            builder = EpubBuilder(self.app.settings)

            orchestrator = DownloadBuildOrchestrator(
                provider, builder, self.app.settings
            )

            result_paths: List[Path] = []
            if content_type_enum == ContentType.WORK:
                result = orchestrator.process_work(target_id)
                if result:
                    result_paths.append(result)
            elif content_type_enum == ContentType.SERIES:
                result_paths = orchestrator.process_series(target_id)
            elif content_type_enum == ContentType.CREATOR:
                result_paths = orchestrator.process_creator(target_id)
            else:
                raise ValueError(
                    f"サポートされていないコンテンツタイプです: {content_type_enum}"
                )

            message = f"{len(result_paths)}件のEPUB生成に成功しました。"
            log.bind(result_count=len(result_paths)).success("タスクが完了しました。")
            return {"status": GuiStatus.SUCCESS, "message": message}

        except Pixiv2EpubError as e:  # 
            log.bind(error=str(e)).error("GUIタスクの処理中にエラーが発生しました。")
            return {"status": GuiStatus.ERROR, "message": str(e)}
        except Exception as e:
            log.bind(error=str(e)).error(
                "GUIタスクの処理中に予期せぬエラーが発生しました。", exc_info=True
            )
            return {"status": GuiStatus.ERROR, "message": f"予期せぬエラーが発生しました: {e}"}

    def setup_bridge(self):
        """Python関数をJavaScriptに公開し、UI注入スクリプトをページに登録します。"""
        try:
            self.page.expose_function("pixiv2epub_run", self._run_task_from_browser)

            injector_path = Path(__file__).parent / "assets" / "injector.js"
            if not injector_path.is_file():
                raise FileNotFoundError(
                    f"インジェクタースクリプトが見つかりません: {injector_path}"
                )

            self.page.add_init_script(path=str(injector_path))

            logger.info(
                "GUIブリッジとインジェクタースクリプトのセットアップが完了しました。"
            )
        except Exception as e:
            logger.bind(error=str(e)).error("GUIブリッジのセットアップに失敗しました。")
            raise
