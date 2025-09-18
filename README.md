<div align="center">
<img src="./pixiv2epub_icon.svg" alt="Pixiv to EPUB Converter Icon" width="250">
<h1>Pixiv to EPUB Converter</h1>
</div>

Pixiv小説をID指定でダウンロードし、高品質なEPUB3形式に変換するコマンドラインツールです。

-----

## ✨ 主な機能

  * **高機能なEPUB3生成**: 小説本文、挿絵、メタデータを取得し、目次や作品情報ページを含む標準規格のEPUB3を生成します。
  * **多彩な実行モード**:
      * 単一の小説ID
      * シリーズ作品の一括処理
      * 特定ユーザーの全作品の一括処理
      * ダウンロードのみ、またはローカルファイルからのビルドのみの実行
  * **Pixiv独自タグ変換**: `[newpage]`, `[chapter:]`, `[[rb:...]]` などのタグを適切に解釈し、XHTMLに変換します。
  * **柔軟な画像処理**: カバー画像と本文中の挿絵を自動で取得・同梱します。`pngquant`などの外部ツールと連携し、ファイルサイズを最適化する画像圧縮も可能です。
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

### 1\. 認証情報の設定

`configs/config.toml.example` をコピーして `configs/config.toml` を作成し、Pixivの **Refresh Token** を設定してください。

```toml:configs/config.toml
[auth]
refresh_token = "your_refresh_token_here"
```

セキュリティのため、ファイルに直接書き込む代わりに**環境変数** `PIXIV_REFRESH_TOKEN` で指定することを強く推奨します。

```bash
export PIXIV_REFRESH_TOKEN="your_refresh_token_here"
```

### 2\. 依存ライブラリのインストール

本ツールは [uv](https://github.com/astral-sh/uv) の利用を推奨しています。以下のコマンドで依存関係をインストールします。

```bash
# uv.lock ファイルから依存関係を同期します
uv sync
```

-----

## 🚀 使い方

`uv run` を使って `main.py` を実行します。

### 単一の小説を処理

```bash
uv run main.py 12345678
```

### 複数の小説を一度に処理

IDをスペース区切りで渡すか、IDを一行ずつ記述したテキストファイルを指定します。

```bash
# IDを直接指定
uv run main.py 12345678 87654321

# ファイルから読み込み
uv run main.py path/to/id_list.txt
```

### シリーズ作品をまとめて処理

`--series` フラグを付けてシリーズIDを指定します。

```bash
uv run main.py --series 98765
```

### ユーザーの全作品をまとめて処理

`--user` フラグを付けてユーザーIDを指定します。シリーズ作品と単独作品が自動で分類され、すべて処理されます。

```bash
uv run main.py --user 58182393
```

### ダウンロード済みデータからEPUBを生成

`--build-only` を使うと、ダウンロード済みのローカルディレクトリからEPUBを生成できます。

```bash
uv run main.py --build-only ./pixiv_raw/作者名/12345678_小説タイトル
```

### メタデータを対話的に編集

`--interactive` フラグを付けると、EPUB生成前にタイトルやあらすじをCLI上で編集できます。

```bash
uv run main.py --interactive 12345678
```

### コマンドラインオプション一覧

```text
usage: main.py [-h] [--user USER_ID | -s SERIES_ID | --build-only RAW_DIR | [inputs ...]] [-c CONFIG] [-v] [-i] [--download-only]

Pixiv小説をダウンロードしてEPUBに変換します。

options:
  -h, --help            このヘルプメッセージを表示して終了します
  -c CONFIG, --config CONFIG
                        設定ファイルのパス (default: ./configs/config.toml)
  -v, --verbose         詳細なログを出力します
  -i, --interactive     ビルド前にメタデータを対話的に編集します (シリーズモードまたはユーザーモードで使用可能)
  --download-only       ダウンロードのみ実行します

入力モード:
  inputs                小説ID(複数可)またはIDリストファイルへのパス
  --user USER_ID        指定したユーザーIDのすべての小説をダウンロードします
  -s SERIES_ID, --series SERIES_ID
                        入力をシリーズIDとして扱います
  --build-only RAW_DIR  指定ディレクトリからビルドのみ実行します
```