# Pixiv to EPUB Converter

<!-- markdownlint-disable MD033 -->
<p align="center">
  <img src="./pixiv2epub_icon.svg" alt="Pixiv to EPUB Converter Icon" width="250">
</p>

<p align="center">
  <!-- Badges -->
  <a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/badge/managed%20by-uv-black.svg?style=flat&labelColor=black" alt="Managed by uv">
  </a>
  <img src="https://img.shields.io/badge/python-3.13%2B-blue.svg?style=flat" alt="Python 3.13+">
</p>

Pixivの小説をURLやIDで指定し、高品質なEPUB形式に変換するコマンドラインツールです。

---

## ✨ 主な機能

- **永続的ライブラリと差分更新**
 一度取得した小説はローカルに永続化されます。二回目以降はコンテンツの変更を自動で検知し、更新があった作品のみをダウンロードするため、高速かつ効率的にライブラリを最新の状態に保てます。

- **安定した書籍管理**
 小説ごとに決定論的なIDをEPUBに付与するため、ファイルを更新しても電子書籍リーダー上で別の本として重複することなく、読書進捗やメモが維持されます。

- **高品質なEPUB3生成**
 小説本文、挿絵、メタデータを取得し、目次や作品情報ページを含むEPUB3を生成します。

- **GUIモード**
 ブラウザを起動し、表示しているPixivの小説ページから直接EPUB化を実行できます。URLをコピー＆ペーストする必要はありません。

- **スマートなURL/ID処理**
 URLやIDを渡すだけで、単一の小説・シリーズ・ユーザー作品かを自動で判別して一括処理します。

- **Pixiv独自タグ変換**
 `[newpage]`, `[chapter:]`, `[[rb:...]]` などのタグを適切に解釈し、XHTMLに変換します。

- **柔軟な画像処理**
 カバー画像と本文中の挿絵を自動で取得・同梱します。pngquantなどの外部ツールと連携し、ファイルサイズを最適化する画像圧縮も可能です。

- **モダンなCLI**
 `Typer`と`rich`ライブラリによる、見やすく直感的なコマンド体系とログ出力を提供します。

---

## 📦 セットアップ

本プロジェクトは [uv](https://github.com/astral-sh/uv) でのパッケージ管理を前提としています。

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

# 4. プロジェクトのセットアップタスクを実行
poe setup
```

`poe setup` コマンドは、`pyproject.toml` に定義されたタスクを実行し、依存関係のインストールと Playwright のセットアップを自動で行います。

---

### 2. Pixiv認証

以下のコマンドを実行するとブラウザが起動します。表示されたウィンドウでPixivにログインしてください。
ログインが成功すると、認証情報がプロジェクトルートの `.env` ファイルと、GUIモード用のセッションファイル (`.gui_session`) に自動で保存されます。

```bash
pixiv2epub auth
```

> **Note**
> この認証ステップは初回のみ必要です。一度 `.env` ファイルが作成されれば、以降のコマンド実行時に自動で読み込まれます。

---

## 🚀 使い方

### 基本的な使い方 (ダウンロード & EPUB生成)

`run` コマンドに小説のURLまたはIDを渡すだけで、ダウンロードからEPUB生成までを一度に行います。

```bash
# 小説のURLを指定
pixiv2epub run "https://www.pixiv.net/novel/show.php?id=12345678"

# シリーズページのURLを指定
pixiv2epub run "https://www.pixiv.net/novel/series/987654"

# ユーザーページのURLを指定 (全作品が対象)
pixiv2epub run "https://www.pixiv.net/users/58182393"
```

---

### GUIモードの使い方

ブラウザ上で直接操作したい場合は `gui` コマンドを使用します。

```bash
pixiv2epub gui
```

このコマンドを実行すると、ログインセッションが保存されたブラウザが起動します。
Pixivの小説・シリーズ・ユーザーのページを開くと、画面上にEPUB化を実行するためのボタンが自動的に追加されます。そのボタンをクリックするだけで、表示中のページの作品をダウンロードし、EPUBを生成できます。

---

### 発展的な使い方

#### ステップ1: ダウンロードのみ実行

```bash
pixiv2epub download "https://www.pixiv.net/novel/show.php?id=12345678"
# > ℹ️ ダウンロードが完了しました: ./.workspace/pixiv_12345678
```

#### ステップ2: ローカルデータからEPUBを生成

```bash
pixiv2epub build ./.workspace/pixiv_12345678
# > ℹ️ ビルドが完了しました: ./epubs/作者名/小説タイトル.epub
```

---

## ⚙️ 設定のカスタマイズ

EPUBの出力先やファイル名の形式などを変更したい場合は、設定ファイルを使用します。

1. `config.example.toml` を `config.toml` などの名前でコピー。
2. コピーしたファイルを編集して設定を変更。
3. `-c` または `--config` オプションで指定。

```bash
pixiv2epub run 12345678 -c config.toml
```

設定可能な項目の詳細は `config.example.toml` を参照してください。

---

## ⌨️ コマンドリファレンス

```bash
Usage: pixiv2epub [OPTIONS] COMMAND [ARGS]...

Pixivの小説をURLやIDで指定し、高品質なEPUB形式に変換するコマンドラインツールです。

Options:
  -v, --verbose                   詳細なデバッグログを有効にします。
  -c, --config FILE               カスタム設定TOMLファイルへのパス。
  --install-completion            現在のシェルに補完機能をインストールします。
  --show-completion               現在のシェル用の補完スクリプトを表示します。
  --help                          このメッセージを表示して終了します。

Commands:
  auth      ブラウザでPixivにログインし、認証トークンとGUIセッションを保存します。
  build     既存のワークスペースディレクトリからEPUBをビルドします。
  download  小説データをワークスペースにダウンロードするだけで終了します。
  gui       ブラウザを起動し、Pixivページ上で直接操作するGUIモードを開始します。
  run       指定されたURLまたはIDの小説をダウンロードし、EPUBをビルドします。
```

### `run`

```text
Usage: pixiv2epub run [OPTIONS] INPUT

  指定されたURLまたはIDの小説をダウンロードし、EPUBをビルドします。

Arguments:
  INPUT  Pixivの小説・シリーズ・ユーザーのURLまたはID。 [required]

Options:
  --help  このメッセージを表示して終了します。
```

### `download`

```text
Usage: pixiv2epub download [OPTIONS] INPUT

  小説データをワークスペースにダウンロードするだけで終了します。

Arguments:
  INPUT  Pixivの小説・シリーズ・ユーザーのURLまたはID。 [required]

Options:
  --help  このメッセージを表示して終了します。
```

### `build`

```text
Usage: pixiv2epub build [OPTIONS] WORKSPACE_PATH

  既存のワークスペースディレクトリからEPUBをビルドします。

Arguments:
  WORKSPACE_PATH  ビルド対象のワークスペースディレクトリへのパス。 [required]

Options:
  --help  このメッセージを表示して終了します。
```

---

## ⚙️ 実行要件

- Python 3.13+
- （任意）画像圧縮ツール: `pngquant`, `jpegoptim`, `cwebp` が PATH 上に必要です。
