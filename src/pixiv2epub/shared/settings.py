# FILE: src/pixiv2epub/shared/settings.py

import tomllib
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from .exceptions import SettingsError


# --- TOMLファイル読み込みロジック ---
def load_toml_config(toml_file: Path) -> Dict[str, Any]:
    """指定されたTOMLファイルを読み込む。"""
    if not toml_file.is_file():
        return {}
    try:
        with toml_file.open("rb") as f:
            return tomllib.load(f)
    except Exception as e:
        raise SettingsError(f"設定ファイル '{toml_file}' の解析に失敗しました: {e}")


def get_project_defaults() -> Dict[str, Any]:
    """pyproject.tomlから[tool.pixiv2epub]セクションを読み込む。"""
    pyproject_path = Path.cwd() / "pyproject.toml"
    config = load_toml_config(pyproject_path)
    return config.get("tool", {}).get("pixiv2epub", {})


class TomlConfigSettingsSource(PydanticBaseSettingsSource):
    """
    ユーザー指定のTOML設定ファイルを読み込むためのカスタムソース。
    """

    def __init__(self, settings_cls: type[BaseSettings], config_file: Optional[Path]):
        super().__init__(settings_cls)
        self.config_file = config_file

    def get_field_value(self, field, field_name):
        return None

    def __call__(self) -> Dict[str, Any]:
        if not self.config_file:
            return {}
        return load_toml_config(self.config_file)


# --- 設定モデル定義 ---
class AuthSettings(BaseModel):
    refresh_token: Optional[str] = Field(None)


class DownloaderSettings(BaseModel):
    api_delay: float = 1.0
    api_retries: int = 3
    overwrite_existing_images: bool = False


class BuilderSettings(BaseModel):
    output_directory: Path = Path("./epubs")
    filename_template: str = "{author_name}/{title}.epub"
    series_filename_template: str = (
        "{author_name}/{series_title}/[{author_name}] {series_title} - {title}.epub"
    )
    cleanup_after_build: bool = True


class PngquantSettings(BaseModel):
    colors: int = 256
    quality: str = "65-90"
    speed: int = 3
    strip: bool = True


class JpegoptimSettings(BaseModel):
    max_quality: int = 85
    strip_all: bool = True
    progressive: bool = True
    preserve_timestamp: bool = True


class CwebpSettings(BaseModel):
    quality: int = 75
    lossless: bool = False
    metadata: str = "none"


class CompressionSettings(BaseModel):
    enabled: bool = True
    skip_if_larger: bool = True
    max_workers: int = 4
    pngquant: PngquantSettings = PngquantSettings()
    jpegoptim: JpegoptimSettings = JpegoptimSettings()
    cwebp: CwebpSettings = CwebpSettings()


class WorkspaceSettings(BaseModel):
    root_directory: Path = Path("./.pixiv2epub_work")


class Settings(BaseSettings):
    """
    アプリケーションの階層的設定管理クラス。
    """

    auth: AuthSettings = AuthSettings()
    downloader: DownloaderSettings = DownloaderSettings()
    builder: BuilderSettings = BuilderSettings()
    compression: CompressionSettings = CompressionSettings()
    workspace: WorkspaceSettings = WorkspaceSettings()
    log_level: str = "INFO"

    _config_file: Optional[Path] = None

    def __init__(self, **values: Any):
        config_file_path = values.pop("_config_file", None)
        self._config_file = Path(config_file_path) if config_file_path else None
        super().__init__(**values)

        if not self.auth.refresh_token:
            raise SettingsError(
                "Pixivのrefresh_tokenが見つかりません。"
                "設定ファイル、.envファイル、または環境変数 (PIXIV2EPUB_AUTH__REFRESH_TOKEN) で設定してください。"
            )

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_prefix="PIXIV2EPUB_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        config_file_path = init_settings.init_kwargs.get("_config_file")
        if config_file_path and not isinstance(config_file_path, Path):
            config_file_path = Path(config_file_path)

        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls, config_file_path),
            get_project_defaults,
        )