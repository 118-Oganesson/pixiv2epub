# src/pixiv2epub/cli.py

import argparse
import logging
from pathlib import Path

from . import api
from .core.exceptions import Pixiv2EpubError
from .core.settings import SettingsError
from .utils.logging import setup_logging
from .utils.url_parser import parse_input


def main():
    parser = argparse.ArgumentParser(
        description="Pixivから小説をダウンロードしてEPUBに変換します。"
    )
    parser.add_argument(
        "url_or_id",
        nargs="?",
        default=None,
        help="小説/シリーズ/ユーザーのURLまたはID。--build-only使用時は不要。",
    )

    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "--download-only",
        action="store_true",
        help="ダウンロードのみ実行し、ビルドは行いません。",
    )
    action_group.add_argument(
        "--build-only",
        metavar="SOURCE_DIR",
        type=Path,
        help="指定したローカルディレクトリのデータからビルドのみ実行します。",
    )

    parser.add_argument(
        "--cleanup",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="EPUB生成後に中間ファイルを削除/保持します。設定ファイルの値より優先されます。",
    )
    parser.add_argument("--config", help="設定ファイルのパス")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="デバッグログを有効にする"
    )
    args = parser.parse_args()

    # CLIとしての引数チェック
    if args.build_only and args.url_or_id:
        parser.error("--build-only を使用する場合、IDやURLは不要です。")
    if not args.build_only and not args.url_or_id:
        parser.error("ID/URLを指定するか、--build-onlyオプションを使用してください。")

    # ログ先行設定
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)

    try:
        # --- API呼び出し時の共通引数 ---
        # api.pyの各関数はSettingsオブジェクトを内部で生成するため、
        # 上書きしたい引数のみをキーワード引数として渡す
        api_kwargs = {"config_path": args.config}
        if args.verbose:
            api_kwargs["log_level"] = "DEBUG"
        if args.cleanup is not None:
            # pydantic-settingsはネストした辞書で設定を上書きできる
            api_kwargs["builder"] = {"cleanup_after_build": args.cleanup}

        # --- 処理の実行 ---
        if args.build_only:
            api.build_novel(args.build_only, **api_kwargs)
            logging.info(f"ビルドが完了しました: {args.build_only}")
            return

        target_type, target_id = parse_input(args.url_or_id)

        if args.download_only:
            logging.info("ダウンロード処理を実行します...")
            if target_type == "novel":
                api.download_novel(target_id, **api_kwargs)
            elif target_type == "series":
                api.download_series(target_id, **api_kwargs)
            elif target_type == "user":
                api.download_user_novels(target_id, **api_kwargs)
        else:  # 通常実行 (Download & Build)
            logging.info("ダウンロードとビルド処理を実行します...")
            if target_type == "novel":
                api.download_and_build_novel(target_id, **api_kwargs)
            elif target_type == "series":
                api.download_and_build_series(target_id, **api_kwargs)
            elif target_type == "user":
                api.download_and_build_user_novels(target_id, **api_kwargs)

        logging.info("処理が正常に完了しました。")

    except (Pixiv2EpubError, SettingsError) as e:
        logging.getLogger("cli").error(f"エラー: {e}")
        exit(1)
    except Exception as e:
        logging.getLogger("cli").critical(
            f"予期せぬ致命的なエラーが発生しました: {e}", exc_info=args.verbose
        )
        exit(1)


if __name__ == "__main__":
    main()
