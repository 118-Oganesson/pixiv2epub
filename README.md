# Pixiv to EPUB Converter

![Pixiv to EPUB Converter Icon](./pixiv2epub_icon.svg){ width=250 }

Pixivの小説をURLやIDで指定し、高品質なEPUB形式に変換するコマンドラインツールです。

-----

## ✨ 主な機能

* **高品質なEPUB3生成**: 小説本文、挿絵、メタデータを取得し、目次や作品情報ページを含むEPUB3を生成します。
* **スマートなURL/ID処理**: URLやIDを渡すだけで、単一の小説・シリーズ・ユーザー作品かを自動で判別して一括処理します。
* **Pixiv独自タグ変換**: `[newpage]`, `[chapter:]`, `[[rb:...]]` などのタグを適切に解釈し、XHTMLに変換します。
* **柔軟な画像処理**: カバー画像と本文中の挿絵を自動で取得・同梱します。`pngquant`などの外部ツールと連携し、ファイルサイズを最適化する画像圧縮も可能です。
* **モダンなCLI**: `rich`ライブラリによる見やすいログ出力や、シンプルなコマンド体系を提供します。

-----

## ⚙️ 実行要件

* **Python 3.13+**
* **ライブラリ:**
  * `pydantic-settings`
  * `pixivpy3`
  * `rich`
  * `Jinja2`
  * その他、`pyproject.toml`を参照
* **（任意）画像圧縮ツール:**
    画像圧縮を有効にする場合、以下のツールのインストールが必要です。
  * `pngquant`
  * `jpegoptim`
  * `cwebp`

-----

## 📦 セットアップ

本プロジェクトは [uv](https://github.com/astral-sh/uv) でのパッケージ管理を前提としています。

### 1\. 依存関係とパッケージのインストール

`uv`を使い、編集可能モードでプロジェクトをインストールします。

```bash
uv pip install -e .
```

### 2\. 認証情報の設定

`.env.example` を `.env` にコピーし、ご自身のPixiv Refresh Tokenを設定してください。

```bash
cp .env.example .env
```

作成した`.env`ファイルを開き、トークンを貼り付けます。

```bash
# .env
# アンダースコアが2つであることに注意してください
PIXIV2EPUB_AUTH__REFRESH_TOKEN="your_refresh_token_here"
```

-----

## 🚀 使い方

インストールが完了すると、`pixiv2epub`コマンドが利用可能になります。

### 単一の小説を処理

小説のURLまたはIDを指定します。

```bash
# URLで指定
pixiv2epub "https://www.pixiv.net/novel/show.php?id=12345678"

# IDで指定
pixiv2epub 12345678
```

### シリーズ作品をまとめて処理

シリーズページのURLを指定します。（自動でシリーズとして認識されます）

```bash
pixiv2epub "https://www.pixiv.net/novel/series/987654"
```

### ユーザーの全作品をまとめて処理

ユーザーページのURLを指定します。（自動でユーザーとして認識されます）

```bash
pixiv2epub "https://www.pixiv.net/users/58182393"
```

### ダウンロード済みデータからEPUBを生成

`--build-only` を使い、ダウンロード済みのローカルディレクトリからEPUBを生成します。

```bash
pixiv2epub --build-only ./pixiv_raw/作者名/12345678_小説タイトル
```

-----

## ⌨️ コマンドラインオプション一覧

```text
usage: cli.py [-h] [--download-only | --build-only SOURCE_DIR] [--cleanup | --no-cleanup] [--config CONFIG] [-v]
              [url_or_id]

Pixivから小説をダウンロードしてEPUBに変換します。

positional arguments:
  url_or_id             小説/シリーズ/ユーザーのURLまたはID。--build-only使用時は不要。

options:
  -h, --help            このヘルプメッセージを表示して終了します
  --download-only       ダウンロードのみ実行し、ビルドは行いません。
  --build-only SOURCE_DIR
                        指定したローカルディレクトリのデータからビルドのみ実行します。
  --cleanup, --no-cleanup
                        EPUB生成後に中間ファイルを削除/保持します。設定ファイルの値より優先されます。
  --config CONFIG       設定ファイルのパス
  -v, --verbose         デバッグログを有効にする
```
