import argparse
import logging
from src.utils.config import load_config
from src.core.downloader import PixivNovelDownloader
from src.core.builder import EpubBuilder
from src.utils.log_setup import setup_logging

from rich.console import Console
from rich.panel import Panel

# ロガーとRichコンソール
logger = logging.getLogger(__name__)
console = Console()


def main():
    """メイン処理"""
    # コマンドライン引数
    parser = argparse.ArgumentParser(
        description="Pixiv小説をダウンロードしてEPUBに変換します。"
    )
    parser.add_argument("novel_id", type=int, help="Pixiv小説ID")
    parser.add_argument(
        "-c", "--config", default="./configs/config.toml", help="設定ファイルのパス"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="詳細なログを出力します"
    )
    args = parser.parse_args()

    # ログ設定
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(level=log_level)

    # ▼ 開始メッセージをPanelで表示
    console.print(
        Panel(
            f"[bold]Novel ID[/]: [cyan]{args.novel_id}[/]\n"
            f"[bold]Config[/]:   [green]{args.config}[/]",
            title="[bold yellow]Pixiv to EPUB Converter[/]",
            expand=False,
        )
    )

    try:
        # 1. 設定読み込み
        logger.debug(f"設定ファイルを読み込みます: {args.config}")
        config = load_config(args.config)

        # 2. 小説ダウンロード
        console.print("\n[yellow]STEP 1: 小説データのダウンロード中...[/]")
        downloader = PixivNovelDownloader(novel_id=args.novel_id, config=config)
        novel_path = downloader.run()
        console.print(f"✅ [bold]ダウンロード完了[/] -> [green]{novel_path}[/]")

        # 3. EPUB生成
        console.print("\n[yellow]STEP 2: EPUBファイルの生成中...[/]")
        builder = EpubBuilder(str(novel_path), config)
        epub_path = builder.create_epub()
        logger.info(f"EPUB生成完了: {epub_path}")

        # ▼ 完了メッセージをPanelで表示
        console.print(
            Panel(
                f"✅ [bold]EPUB successfully created![/]\n[green]{epub_path}[/]",
                title="[bold green]Success[/]",
                expand=False,
            )
        )

    except (FileNotFoundError, ValueError) as e:
        logger.error(f"エラーが発生しました: {e}")
    except Exception:
        # rich_tracebacks=True の設定が有効なら、分かりやすく表示される
        logger.exception("予期せぬエラーが発生しました。")


if __name__ == "__main__":
    main()
