# FILE: src/pixiv2epub/gui.py
from pathlib import Path

from loguru import logger
from playwright.sync_api import Page

from ...app import Application
from ...domain.exceptions import InvalidInputError
from ...utils.url_parser import parse_input


class GuiManager:
    """GUIモードのバックエンドロジックを管理し、Playwrightページと連携します。"""

    def __init__(self, page: Page, app: Application):
        self.page = page
        self.app = app

    async def _run_task_from_browser(self, url: str) -> dict:
        """ブラウザから呼び出される非同期ラッパー関数。"""
        logger.info(f"ブラウザからタスク実行リクエスト: {url}")
        try:
            # 既存のURLパーサーを再利用して、IDとタイプを特定
            target_type, target_id = parse_input(url)

            message = f"処理を開始します: タイプ={target_type}, ID={target_id}"
            logger.info(message)

            # Applicationクラスの同期メソッドを呼び出す
            if target_type == "novel":
                result_path = self.app.run_novel(target_id)
                message = f"EPUBの生成に成功しました: {result_path}"
            elif target_type == "series":
                result_paths = self.app.run_series(target_id)
                message = (
                    f"シリーズ内の {len(result_paths)} 件のEPUB生成に成功しました。"
                )
            elif target_type == "user":
                result_paths = self.app.run_user_novels(target_id)
                message = f"ユーザーの {len(result_paths)} 件のEPUB生成に成功しました。"
            else:
                # このケースは通常発生しないはず
                raise InvalidInputError(f"未対応のターゲットタイプです: {target_type}")

            logger.info(f"タスク完了: {message}")
            return {"status": "success", "message": message}

        except Exception as e:
            logger.error(f"GUIタスクの処理中にエラーが発生しました: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def setup_bridge(self):
        """Python関数をJavaScriptに公開し、UI注入スクリプトをページに登録します。"""
        try:
            # 'pixiv2epub_run'という名前でPythonのメソッドをwindowオブジェクトに公開
            self.page.expose_function("pixiv2epub_run", self._run_task_from_browser)

            # injector.jsの絶対パスを解決
            injector_path = Path(__file__).parent / "assets" / "gui" / "injector.js"
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
