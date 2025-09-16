# Pixiv to EPUB Converter

Pixiv小説をID指定でダウンロードし、高品質なEPUB3形式に変換するコマンドラインツールです。

## ✨ 主な機能

  * **高機能なEPUB3生成**: 小説本文、挿絵、メタデータを取得し、目次や作品情報ページを含む標準規格のEPUB3を生成します。
  * **Pixiv独自タグ変換**: `[newpage]`, `[chapter:]`, `[[rb:...]]` などのタグを適切に解釈し、XHTMLに変換します。
  * **柔軟な画像処理**: カバー画像と本文中の挿絵を自動で取得・同梱します。`pngquant`などの外部ツールと連携し、ファイルサイズを最適化する画像圧縮も可能です。
  * **多彩な実行モード**: 単一作品、シリーズ作品の一括処理、ダウンロードのみ、ローカルファイルからのビルドのみなど、柔軟な実行が可能です。
  * **洗練されたCLI**: `rich`ライブラリによる進捗表示や、ビルド前の対話的なメタデータ編集機能を提供します。

-----

## ⚙️ 実行要件

  * **Python 3.13+**
  * **ライブラリ:**
      * `pixivpy3`
      * `rich`
      * `beautifulsoup4`
      * `Jinja2`
  * **（任意）画像圧縮ツール:**
    `config.toml`で画像圧縮を有効にする場合、以下のツールのインストールが必要です。
      * `pngquant`
      * `jpegoptim`
      * `cwebp`

-----

## 📦 セットアップ

1.  **認証情報の設定**

    `configs/config.toml.example` をコピーして `configs/config.toml` を作成し、Pixivの **Refresh Token** を設定してください。

    ```toml:configs/config.toml
    [auth]
    refresh_token = "your_refresh_token_here"
    ```

    セキュリティのため、ファイルに直接書き込む代わりに**環境変数**で指定することを推奨します。

    ```bash
    export PIXIV_REFRESH_TOKEN="your_refresh_token_here"
    ```

2.  **依存ライブラリのインストール**

    本ツールは [uv](https://github.com/astral-sh/uv) の利用を推奨しています。

    ```bash
    # uvをインストールしていない場合
    pip install uv

    # 依存ライブラリをインストール
    uv pip install -r requirements.txt
    ```

-----

## 🚀 使い方

環境を有効化した後、`main.py` を実行します。

#### **単一の小説を処理**

```bash
uv run main.py 12345678
```

#### **複数の小説を一度に処理**

IDをスペース区切りで渡すか、IDを一行ずつ記述したテキストファイルを指定します。

```bash
# IDを直接指定
uv run main.py 12345678 87654321

# ファイルから読み込み
uv run main.py path/to/id_list.txt
```

#### **シリーズ作品をまとめて処理**

`--series` フラグを付けてシリーズIDを指定します。

```bash
uv run main.py --series 98765
```

#### **ダウンロード済みデータからEPUBを生成**

`--build-only` を使うと、ダウンロード済みのローカルディレクトリからEPUBを生成できます。

```bash
uv run main.py --build-only ./outputs/raw/YourNovelTitle_12345678
```

#### **メタデータを対話的に編集**

`--interactive` フラグを付けると、EPUB生成前にタイトルやあらすじをCLI上で編集できます。

```bash
uv run main.py --interactive 12345678
```

### **コマンドラインオプション一覧**

```text
usage: main.py [-h] [-c CONFIG] [-v] [-i] [-s] [--download-only | --build-only RAW_DIR] [inputs ...]

Pixiv小説をダウンロードしてEPUBに変換します。

positional arguments:
  inputs                小説ID(複数可)またはIDリストファイルへのパス

options:
  -h, --help            このヘルプメッセージを表示して終了します
  -c, --config CONFIG   設定ファイルのパスを指定します (default: ./configs/config.toml)
  -v, --verbose         詳細なログを出力します
  -i, --interactive     ビルド前にメタデータを対話的に編集します
  -s, --series          入力をシリーズIDとして扱います
  --download-only       ダウンロードのみ実行します
  --build-only RAW_DIR  指定ディレクトリからビルドのみ実行します
```