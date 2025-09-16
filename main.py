"""
Pixiv小説ダウンローダー＆EPUBコンバーターのメインスクリプト。

コマンドラインインターフェースを提供し、指定された小説IDやシリーズIDに基づいて
小説データをダウンロードし、EPUBファイルとして整形・出力します。

主な機能:
- 単一または複数の小説IDを指定して処理
- シリーズIDを指定してシリーズ作品をまとめて処理
- ダウンロード済みのデータからEPUBを生成
- EPUB生成前にメタデータを対話的に編集
"""

import argparse
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional

from src.utils.config import load_config
from src.core.downloader import PixivNovelDownloader, PixivSeriesDownloader
from src.core.builder import EpubBuilder
from src.utils.log_setup import setup_logging

from rich.console import Console
from rich.panel import Panel

logger = logging.getLogger(__name__)
console = Console()


def interactive_edit_metadata(detail_path: Path) -> Optional[Dict[str, Any]]:
    """
    `detail.json`の内容を対話的に編集します。

    ユーザーにタイトル、作者名、あらすじの変更を促し、
    変更があった場合のみファイルを更新して、新しいメタデータ辞書を返します。

    Args:
        detail_path (Path): 編集対象の`detail.json`ファイルへのパス。

    Returns:
        Optional[Dict[str, Any]]: 変更が加えられた場合に、更新後のメタデータ辞書を返します。
                                 変更がなかった場合や、ファイルが存在しない場合はNoneを返します。
    """
    if not detail_path.is_file():
        logger.error(f"メタデータファイルが見つかりません: {detail_path}")
        return None

    console.print("\n[cyan]-- メタデータ編集モード --[/]")

    with open(detail_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 編集対象のフィールドを定義: (表示ラベル, データ内のキー階層)
    editable_fields = {
        "title": ("小説タイトル", ["title"]),
        "author": ("作者名", ["authors", "name"]),
        "description": ("あらすじ", ["description"]),
    }

    made_changes = False
    for key, (label, path_keys) in editable_fields.items():
        try:
            # ネストされた辞書から値を取得
            temp = data
            for p_key in path_keys:
                temp = temp[p_key]
            current_value = str(temp)
        except (KeyError, TypeError):
            logger.warning(f"編集対象のキーが見つかりません: {'.'.join(path_keys)}")
            continue

        display_value = current_value.replace("\n", " ").strip()
        console.print(f"[bold]{label}[/]: [dim]{display_value[:70]}...[/]")

        new_value = console.input("新しい値を入力 (変更しない場合はEnter): ").strip()

        if new_value:
            # ネストされた辞書の値を更新
            temp = data
            for p_key in path_keys[:-1]:
                temp = temp[p_key]
            temp[path_keys[-1]] = new_value
            console.print("  -> [green]更新しました[/]")
            made_changes = True

    if made_changes:
        with open(detail_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        console.print("✅ [bold]メタデータをファイルに保存しました。[/]")
        return data

    console.print("メタデータに変更はありませんでした。")
    return None


def build_from_path(novel_path: Path, config: dict, args: argparse.Namespace):
    """
    指定されたローカルパスからEPUBを生成します。

    `detail.json`を含むディレクトリパスを受け取り、EpubBuilderを初期化して
    EPUB生成プロセスを実行します。

    Args:
        novel_path (Path): `detail.json`が格納されている小説データディレクトリのパス。
        config (dict): アプリケーション全体の設定情報。
        args (argparse.Namespace): コマンドライン引数。
                                   `--interactive`フラグの判定に使用します。
    """
    if not (novel_path / "detail.json").exists():
        logger.error(
            f"指定されたディレクトリに detail.json が見つかりません: {novel_path}"
        )
        return

    console.print(f"\n[yellow]EPUB生成中: {novel_path.name}[/]")

    custom_meta = None
    if args.interactive:
        custom_meta = interactive_edit_metadata(novel_path / "detail.json")

    builder = EpubBuilder(str(novel_path), config, custom_metadata=custom_meta)
    epub_path = builder.create_epub()

    console.print(
        Panel(
            f"✅ [bold]EPUB successfully created![/]\n[green]{epub_path}[/]",
            title="[bold green]Success[/]",
            expand=False,
        )
    )


def process_single_novel(novel_id: int, config: dict, args: argparse.Namespace):
    """
    単一の小説IDに対してダウンロードからビルドまでの一連の処理を実行します。

    Args:
        novel_id (int): 処理対象のPixiv小説ID。
        config (dict): アプリケーション全体の設定情報。
        args (argparse.Namespace): コマンドライン引数。
                                   `--download-only`フラグの判定に使用します。
    """
    console.print("\n[yellow]STEP 1: 小説データのダウンロード中...[/]")
    downloader = PixivNovelDownloader(novel_id=novel_id, config=config)
    novel_path = downloader.run()
    console.print(f"✅ [bold]ダウンロード完了[/] -> [green]{novel_path}[/]")

    if not args.download_only:
        build_from_path(novel_path, config, args)


def main():
    """
    コマンドライン引数を解析し、アプリケーションのメイン処理を実行します。
    """
    parser = argparse.ArgumentParser(
        description="Pixiv小説をダウンロードしてEPUBに変換します。",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "inputs", nargs="*", help="小説ID(複数可)またはIDリストファイルへのパス"
    )
    parser.add_argument(
        "-c", "--config", default="./configs/config.toml", help="設定ファイルのパス"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="詳細なログを出力します"
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="ビルド前にメタデータを対話的に編集します",
    )
    parser.add_argument(
        "-s", "--series", action="store_true", help="入力をシリーズIDとして扱います"
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--download-only", action="store_true", help="ダウンロードのみ実行します"
    )
    mode_group.add_argument(
        "--build-only",
        type=str,
        metavar="RAW_DIR",
        help="指定ディレクトリからビルドのみ実行します",
    )

    args = parser.parse_args()

    setup_logging(level="DEBUG" if args.verbose else "INFO")

    console.print(Panel("[bold yellow]Pixiv to EPUB Converter[/]", expand=False))

    try:
        config = load_config(args.config)

        # --- シリーズ処理モード ---
        if args.series:
            if not args.inputs:
                parser.error("処理対象のシリーズIDを指定してください。")

            series_id = int(args.inputs[0])
            console.print(
                f"シリーズモードで実行します。シリーズID: [cyan]{series_id}[/]"
            )

            series_downloader = PixivSeriesDownloader(series_id, config)
            downloaded_paths = series_downloader.run(interactive=args.interactive)

            if not args.download_only and downloaded_paths:
                console.rule("[bold yellow]Starting Series Build Process[/]")
                for i, path in enumerate(downloaded_paths, 1):
                    console.print(f"\n[bold]Building {i}/{len(downloaded_paths)}[/]")
                    try:
                        build_from_path(path, config, args)
                    except Exception:
                        logger.exception(
                            f"パス {path} のビルド中にエラーが発生しました。"
                        )
                        console.print(
                            f"❌ [red]パス {path.name} のビルドに失敗しました。[/]"
                        )
            return

        # --- ビルド専用モード ---
        if args.build_only:
            logger.info(f"ビルド専用モードで実行します: {args.build_only}")
            build_path = Path(args.build_only).resolve()
            build_from_path(build_path, config, args)
            return

        # --- 入力IDの解決 ---
        if not args.inputs:
            parser.error("処理対象の小説IDまたはIDリストファイルを指定してください。")

        novel_ids = []
        input_path = Path(args.inputs[0])
        # 入力がファイルパスであり、かつそれが一つだけ指定されている場合、
        # ファイルからIDリストを読み込む
        if len(args.inputs) == 1 and input_path.is_file():
            logger.info(f"ファイルからIDを読み込みます: {input_path}")
            with open(input_path, "r", encoding="utf-8") as f:
                novel_ids = [int(line.strip()) for line in f if line.strip().isdigit()]
        else:
            # それ以外の場合は、引数を直接IDとして解釈する
            novel_ids = [int(val) for val in args.inputs if val.isdigit()]

        if not novel_ids:
            logger.error("処理対象の小説IDが見つかりません。")
            return

        # --- メインループ (単一小説処理) ---
        total = len(novel_ids)
        logger.info(f"計 {total} 件の小説を処理します。")
        for i, novel_id in enumerate(novel_ids, 1):
            console.rule(f"[bold]Processing {i}/{total}[/]")
            console.print(f"Novel ID: [cyan]{novel_id}[/]")
            try:
                process_single_novel(novel_id, config, args)
            except Exception:
                logger.exception(
                    f"小説ID {novel_id} の処理中に予期せぬエラーが発生しました。"
                )
                console.print(
                    f"❌ [red]小説ID {novel_id} の処理に失敗しました。次の処理に進みます。[/]"
                )

        console.rule("[bold green]All tasks completed![/]")

    except (FileNotFoundError, ValueError) as e:
        logger.error(f"設定ファイルや入力ファイルが見つからないか、値が不正です: {e}")
    except Exception:
        logger.exception("予期せぬエラーが発生しました。")


if __name__ == "__main__":
    main()
