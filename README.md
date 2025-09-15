# Pixiv to EPUB Converter

Pixiv小説をID指定でダウンロードし、高品質なEPUB3形式に変換するコマンドラインツールです。

## 🚀 使い方

1.  **設定**
    `configs/config.toml.example`をベースに`configs/config.toml` を作成し、Pixivの **Refresh Token** を設定してください。
    環境変数 `PIXIV_REFRESH_TOKEN` で指定することも可能です（推奨）。

    ```toml:configs/config.toml
    [auth]
    refresh_token = "your_refresh_token_here"
    ```

2.  **実行**
    環境を有効化した後、`main.py` を実行します。

    ```bash
    uv run main.py <小説ID>
    ```

    ```

    **オプション:**

      * `-c`, `--config`: 設定ファイルのパスを指定します。
      * `-v`, `--verbose`: 詳細なデバッグログを出力します。

-----

## ⚙️ 実行要件

  * **Python 3.13+**

  * **ライブラリ:**

      * `pixivpy3`
      * `rich`
      * `beautifulsoup4`
      * `Jinja2`

  * **（任意）画像圧縮ツール:**
    `config.toml` で画像圧縮を有効にする場合、以下のツールが必要です。

      * `pngquant`
      * `jpegoptim`
      * `cwebp`

-----

## ✨ 機能概要

  * **EPUB3生成**: 小説本文、挿絵、メタデータを取得し、標準規格のEPUB3を生成します。
  * **Pixivタグ変換**: `[chapter:]` や `[[rb:...]]` などの独自タグをHTMLに変換します。
  * **画像処理**: カバー画像と本文中の挿絵を自動で取得・同梱します。オプションでファイルサイズを削減する画像圧縮も可能です。
  * **CLI**: `rich`によるプログレスバー表示など、分かりやすいインターフェースを提供します。
  