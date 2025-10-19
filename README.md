# Pixiv/Fanbox to EPUB Converter (piep)

<!-- markdownlint-disable MD033 -->
<p align="center">
  <img src="./icon/piep.svg" alt="Pixiv/Fanbox to EPUB Converter Icon" width="250">
</p>

<p align="center">
  <a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/badge/managed%20by-uv-black.svg?style=flat&labelColor=black" alt="Managed by uv">
  </a>
  <img src="https://img.shields.io/badge/python-3.13%2B-blue.svg?style=flat" alt="Python 3.13+">
</p>

Pixivの小説やFanboxの投稿をURLやIDで指定し、高品質なEPUB形式に変換するコマンドラインツールです。

---

## ✨ 主な機能

- **マルチプロバイダ対応**: Pixiv (小説) と Fanbox (投稿) の両方に対応。
- **永続的ライブラリと差分更新**: 一度取得したコンテンツはローカルに永続化され、更新がある作品のみを再取得。
- **安定した書籍管理**: 決定論的なID付与により、電子書籍リーダー上で重複せず読書進捗を保持。
- **高品質なEPUB3生成**: 本文・挿絵・メタデータを含むEPUB3を生成。
- **GUIモード**: ブラウザ上でPixivやFanboxページを直接操作してEPUB化可能。
- **スマートなURL/ID処理**: URLまたはIDを渡すだけで、自動的に対象を判別して一括処理。
- **Pixiv独自タグ変換**: `[newpage]`, `[chapter:]`, `[[rb:...]]` などを正確にXHTMLへ変換。
- **柔軟な画像処理**: pngquant等の外部ツールと連携し画像圧縮を自動化。
- **モダンなCLI**: `Typer` + `rich` による見やすく直感的なUI。

---

## 📦 セットアップ

本プロジェクトは [uv](https://github.com/astral-sh/uv) によるパッケージ管理を前提としています。

### 1. リポジトリのクローンと環境構築

```bash
# 1. リポジトリをクローン
git clone https://github.com/118-Oganesson/pixiv2epub.git
cd pixiv2epub

# 2. uvで仮想環境を作成し、有効化
uv venv
source .venv/bin/activate  # macOS / Linux
# .venv\Scripts\activate   # Windows

# 3. 依存関係をインストール
uv sync

# 4. Playwrightなどのセットアップを実行
poe setup
```

`poe setup` は `pyproject.toml` に定義されたセットアップタスクを自動で実行します。

---

### 2. 認証

#### Pixiv認証

以下のコマンドを実行するとブラウザが起動し、Pixivログイン後に認証情報が `.env` と `.gui_session` に保存されます。

```bash
pixiv2epub auth pixiv
```

#### Fanbox認証

同様に以下でFanboxログインを行います。

```bash
pixiv2epub auth fanbox
```

> **Note**
> 認証は初回のみ必要です。`.env` が作成されれば以降は自動で使用されます。

---

## 🚀 使い方

### 基本的な使い方 (ダウンロード & EPUB生成)

```bash
# Pixiv小説
pixiv2epub run "https://www.pixiv.net/novel/show.php?id=12345678"

# Pixivシリーズ
pixiv2epub run "https://www.pixiv.net/novel/series/987654"

# Pixivユーザー全作品
pixiv2epub run "https://www.pixiv.net/users/58182393"

# Fanbox投稿
pixiv2epub run "https://creator.fanbox.cc/posts/123456"

# Fanboxクリエイター全投稿
pixiv2epub run "https://creator.fanbox.cc/"
# または
pixiv2epub run "https://www.fanbox.cc/@creator"
```

---

### GUIモードの使い方

```bash
# Pixivを開く (デフォルト)
pixiv2epub gui pixiv
# または
pixiv2epub gui

# Fanboxを開く
pixiv2epub gui fanbox
```

コマンド実行後、ログイン済みブラウザが起動し、ページ上に「EPUB化」ボタンが自動追加されます。

---

### 発展的な使い方

#### ステップ1: ダウンロードのみ実行

```bash
pixiv2epub download "https://www.pixiv.net/novel/show.php?id=12345678"
# > ℹ️ ダウンロードが完了しました: ./.workspace/pixiv_12345678
```

#### ステップ2: ローカルデータからEPUB生成

```bash
pixiv2epub build ./.workspace/pixiv_12345678
# > ℹ️ ビルドが完了しました: ./epubs/作者名/小説タイトル.epub
```

---

## ⚙️ 設定のカスタマイズ

EPUB出力先などを変更したい場合は設定ファイルを使用します。

1. `config.example.toml` をコピーして `config.toml` を作成  
2. 設定を編集  
3. `-c` または `--config` で指定  

```bash
pixiv2epub run <URL_or_ID> -c config.toml
```

設定項目の詳細は `config.example.toml` を参照。

---

## ⌨️ コマンドリファレンス

```bash
Usage: pixiv2epub [OPTIONS] COMMAND [ARGS]...

PixivやFanboxの作品をURLやIDで指定し、高品質なEPUB形式に変換するコマンドラインツールです。

Options:
  -v, --verbose                   詳細なデバッグログを有効にします。
  -c, --config FILE               カスタム設定TOMLファイルへのパス。
  --log-file                      ログをJSON形式で出力します。
  --install-completion            シェル補完機能をインストールします。
  --show-completion               現在のシェル用補完スクリプトを表示します。
  --help                          このメッセージを表示して終了します。

Commands:
  auth      認証情報を保存します (pixiv/fanbox)。
  build     ワークスペースからEPUBをビルドします。
  download  データをワークスペースに保存のみします。
  gui       ブラウザ上で操作するGUIモードを起動します。
  run       ダウンロードとEPUBビルドをまとめて実行します。
```

---

## ⚙️ 実行要件

- Python 3.13+
- （任意）画像圧縮ツール: `pngquant`, `jpegoptim`, `cwebp` がPATHに存在すること

---

## 💻 インストールコマンド

お使いのオペレーティングシステムに応じて、以下のコマンドをターミナル（またはコマンドプロンプト）で実行してください。

### Linux (APT)

DebianやUbuntuなど、APTパッケージマネージャを使用するLinuxディストリビューション向けのコマンドです。

```bash
sudo apt update
sudo apt install pngquant jpegoptim webp
```

> 補足: `webp` パッケージには `cwebp` コマンドが含まれています。

### Mac (Homebrew)

macOS用のパッケージマネージャであるHomebrewを使用します。

```bash
brew install pngquant jpegoptim webp
```

### Windows (Scoop)

Windows用のコマンドラインインストーラであるScoopを使用します。

```bash
scoop install pngquant jpegoptim webp
```
