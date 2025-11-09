# src/pixiv2epub/shared/themes.py (新設)
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

# --- 1. 定義 (Dataclasses) ---


@dataclass(frozen=True)
class ThemeStrings:
    """
    ローカライズ可能なUI文字列。
    `nav.xhtml.j2` や `component_generator.py` がこれを参照する。
    """

    INFO_PAGE_TITLE: str = '作品情報'
    TOC_TITLE: str = '目次'
    LANDMARKS_TITLE: str = 'ランドマーク'
    COVER_TITLE: str = '表紙'
    BODY_MATTER_TITLE: str = '本文開始'
    UNSUPPORTED_BLOCK: str = 'サポートされていないコンテンツブロックは表示できません。'


@dataclass(frozen=True)
class ThemeTemplates:
    """
    ビルダーが参照するテンプレートファイル名の定義。
    `component_generator.py` がこれを参照する。
    """

    CSS: str = 'style.css.j2'
    INFO_PAGE: str = 'info_page.xhtml.j2'
    PAGE_WRAPPER: str = 'page_wrapper.xhtml.j2'
    CONTENT_OPF: str = 'content.opf.j2'
    NAV: str = 'nav.xhtml.j2'
    COVER_PAGE: str = 'cover_page.xhtml.j2'


@dataclass(frozen=True)
class Theme:
    """
    単一のテーマ定義。
    Pythonネイティブな `theme.toml` の代替。
    """

    name: str
    path: Path  # このテーマのテンプレートが格納されている
    # (例:.../assets/epub/default)
    strings: ThemeStrings = field(default_factory=ThemeStrings)
    templates: ThemeTemplates = field(default_factory=ThemeTemplates)


# --- 2. 設定 (Instances) ---

# assets/epub/ 構成に基づくパス
ASSETS_ROOT = Path(__file__).parent.parent / 'assets' / 'epub'

# デフォルトテーマの定義
DEFAULT_THEME: Final = Theme(
    name='default',
    path=ASSETS_ROOT / 'default',
    # strings と templates はデフォルト値を使用
)

# Pixivテーマの定義
PIXIV_THEME: Final = Theme(
    name='pixiv',
    path=ASSETS_ROOT / 'pixiv',
    templates=ThemeTemplates(
        # (修正) 小文字の `info_page` を `INFO_PAGE` に変更
        INFO_PAGE='info_page.xhtml.j2',  # pixiv/info_page.xhtml.j2 を使用
        CSS='style.css.j2',  # pixiv/style.css.j2 を使用
        # 他のテンプレートは default が使われる(BuilderのChoiceLoaderが処理)
    ),
)

# --- 3. 参照 (Public API) ---
THEME_MAP: Final[Mapping[str, Theme]] = {
    'default': DEFAULT_THEME,
    'pixiv': PIXIV_THEME,
    'fanbox': DEFAULT_THEME,  # Fanboxは現在デフォルトを使用
}


def get_theme_config(provider_name: str) -> Theme:
    """プロバイダ名に基づいて適切なテーマ設定を返す"""
    return THEME_MAP.get(provider_name, DEFAULT_THEME)
