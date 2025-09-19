#
# -----------------------------------------------------------------------------
# pixiv2epub/src/pixiv2epub/cli.py
#
# コマンドラインインターフェース（CLI）のエントリーポイント。
# argparseを用いてコマンドライン引数を解析し、api.pyで定義された
# 高レベル関数を呼び出す責務を持ちます。
# -----------------------------------------------------------------------------
import argparse
import sys
import logging

from . import api

logger = logging.getLogger("pixiv2epub")


def main():
    """CLIのメイン処理"""
    parser = argparse.ArgumentParser(
        description="Pixivの小説をダウンロードしてEPUBに変換します。",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-c", "--config", type=str, help="設定ファイルのパスを指定します。"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="デバッグ用の詳細なログを出力します。",
    )

    # サブコマンドのパーサーを作成
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="実行するコマンド"
    )

    # 'novel' コマンド
    parser_novel = subparsers.add_parser(
        "novel", help="単一の小説を処理します。\n例: pixiv2epub novel 1234567"
    )
    parser_novel.add_argument("id", type=int, help="Pixivの小説ID")

    # 'series' コマンド
    parser_series = subparsers.add_parser(
        "series", help="小説シリーズを処理します。\n例: pixiv2epub series 891011"
    )
    parser_series.add_argument("id", type=int, help="PixivのシリーズID")

    # 'user' コマンド
    parser_user = subparsers.add_parser(
        "user", help="ユーザーの全作品を処理します。\n例: pixiv2epub user 12345"
    )
    parser_user.add_argument("id", type=int, help="PixivのユーザーID")

    args = parser.parse_args()
    log_level = "DEBUG" if args.verbose else "INFO"

    try:
        if args.command == "novel":
            logger.info(f"小説ID: {args.id} の処理を開始します...")
            output_path = api.download_and_build_novel(
                novel_id=args.id, config_path=args.config, log_level=log_level
            )
            logger.info("✅ 処理完了")
            print(f"作成されたファイル: {output_path}")

        elif args.command == "series":
            logger.info(f"シリーズID: {args.id} の処理を開始します...")
            output_paths = api.download_and_build_series(
                series_id=args.id, config_path=args.config, log_level=log_level
            )
            logger.info("✅ シリーズ処理完了")
            print("作成されたファイル:")
            for path in output_paths:
                print(f"  - {path}")

        elif args.command == "user":
            logger.info(f"ユーザーID: {args.id} の全作品の処理を開始します...")
            output_paths = api.download_and_build_user_novels(
                user_id=args.id, config_path=args.config, log_level=log_level
            )
            logger.info("✅ ユーザー作品処理完了")
            print("作成されたファイル:")
            for path in output_paths:
                print(f"  - {path}")

    except Exception as e:
        # api層で詳細なエラーログは出力済みのため、CLIではシンプルなメッセージを表示
        logger.critical(f"❌ 致命的なエラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
