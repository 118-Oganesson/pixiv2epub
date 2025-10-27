# FILE: src/pixiv2epub/shared/settings.py

import tomllib
from pathlib import Path
from typing import Any, cast

from pydantic import (
    BaseModel,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
)
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from .exceptions import SettingsError


# --- TOMLファイル読み込みロジック ---
def load_toml_config(toml_file: Path) -> dict[str, Any]:
    """指定されたTOMLファイルを読み込みます。"""
    if not toml_file.is_file():
        return {}
    try:
        with toml_file.open('rb') as f:
            return tomllib.load(f)
    except Exception as e:
        raise SettingsError(
            f"設定ファイル '{toml_file}' の解析に失敗しました: {e}"
        ) from e


class TomlConfigSettingsSource(PydanticBaseSettingsSource):
    """ユーザー指定のTOML設定ファイルを読み込むためのカスタムソース。"""

    def __init__(self, settings_cls: type[BaseSettings], config_file: Path | None):
        super().__init__(settings_cls)
        self.config_file = config_file
        self._toml_config: dict[str, Any] = (
            load_toml_config(self.config_file) if self.config_file else {}
        )

    def get_field_value(self, field: object, field_name: str) -> tuple[Any, str, bool]:
        """このカスタムソースはフィールドごとの値取得をサポートしないため、__call__に処理を委ねます。"""
        # Pydanticの仕様に合わせ、(値, キー, 複合的か)のタプルを返す
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        """設定ファイル全体を辞書として一度に返します。"""
        return self._toml_config


class PyProjectTomlSource(PydanticBaseSettingsSource):
    """pyproject.tomlから[tool.pixiv2epub]セクションを読み込むソース。"""

    def __init__(self, settings_cls: type[BaseSettings]):
        super().__init__(settings_cls)
        self._config = self._load_pyproject_toml()

    def _load_pyproject_toml(self) -> dict[str, Any]:
        """pyproject.tomlから[tool.pixiv2epub]セクションを読み込みます。"""
        pyproject_path = Path.cwd() / 'pyproject.toml'
        config = load_toml_config(pyproject_path)  # 既存のヘルパーを利用
        return cast(dict[str, Any], config.get('tool', {}).get('pixiv2epub', {}))

    def get_field_value(self, field: object, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._config


# --- 設定モデル定義 ---


class PixivAuthSettings(BaseModel):
    """Pixiv認証に特化した設定モデル。"""

    refresh_token: SecretStr | None = Field(
        default=None,
        description='Pixiv APIのリフレッシュトークン。',
    )
    client_id: SecretStr = Field(
        default=SecretStr('MOBrBDS8blbauoSck0ZfDbtuzpyT'),
        description='Pixiv APIのクライアントID。',
    )
    client_secret: SecretStr = Field(
        default=SecretStr('lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj'),
        description='Pixiv APIのクライアントシークレット。',
    )
    user_agent: str = Field(
        default='PixivIOSApp/7.13.3 (iOS 14.6; iPhone13,2)',
        description='APIリクエストに使用するユーザーエージェント。',
    )
    login_url: str = Field(
        default='https://app-api.pixiv.net/web/v1/login',
        description='ログインページのURL。',
    )
    auth_token_url: str = Field(
        default='https://oauth.secure.pixiv.net/auth/token',
        description='認証トークン取得エンドポイント。',
    )
    redirect_uri: str = Field(
        default='https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback',
        description='OAuthリダイレクトURI。',
    )

    @field_validator('refresh_token')
    @classmethod
    def validate_token_is_not_placeholder(
        cls, value: SecretStr | None
    ) -> SecretStr | None:
        if value is None:
            return None
        secret_value = value.get_secret_value()
        if not secret_value or 'your_refresh_token_here' in secret_value:
            raise ValueError(
                '無効なPixivプレースホルダートークンが検出されました。'
                " 'auth' コンドを実行するか、設定を更新してください。"
            )
        return value


class FanboxAuthSettings(BaseModel):
    """Fanbox認証に特化した設定モデル。"""

    sessid: SecretStr | None = Field(
        default=None,
        description='FANBOXにログインした際のFANBOXSESSIDクッキー。',
    )
    base_url: str = Field(
        default='https://api.fanbox.cc/',
        description='Fanbox APIのベースURL。',
    )

    @field_validator('sessid')
    @classmethod
    def validate_sessid_is_not_placeholder(
        cls, value: SecretStr | None
    ) -> SecretStr | None:
        if value is None:
            return None
        secret_value = value.get_secret_value()
        if not secret_value or 'your_fanbox_sessid_here' in secret_value:
            raise ValueError(
                '無効なFanboxプレースホルダートークンが検出されました。'
                " 'auth' コマンドを実行するか、設定を更新してください。"
            )
        return value


class ProviderSettings(BaseModel):
    """各プロバイダの設定をまとめるモデル。"""

    pixiv: PixivAuthSettings = Field(default_factory=PixivAuthSettings)
    fanbox: FanboxAuthSettings = Field(default_factory=FanboxAuthSettings)


class CircuitBreakerSettings(BaseModel):
    """サーキットブレーカーに関する設定。"""

    fail_max: int = Field(
        default=5,
        description='何回連続で失敗したらサーキットをOpen状態にするか。',
    )
    reset_timeout: int = Field(
        default=60,
        description='サーキットがOpenしてからHalf-Open状態に移行するまでの秒数。',
    )


class DownloaderSettings(BaseModel):
    """ダウンロード処理に関する設定。"""

    api_delay: float = Field(default=1.0, description='APIリクエスト間の遅延時間(秒)。')
    api_retries: int = Field(
        default=3,
        description='APIリクエストが失敗した場合のリトライ回数。',
    )
    overwrite_existing_images: bool = Field(
        default=False,
        description='同名の画像が既に存在する場合に上書きするかどうか。',
    )
    circuit_breaker: CircuitBreakerSettings = Field(
        default_factory=CircuitBreakerSettings
    )


class BuilderSettings(BaseModel):
    """EPUB生成処理に関する設定。"""

    output_directory: Path = Field(
        default=Path('./epubs'),
        description='生成されたEPUBファイルの保存先ディレクトリ。',
    )
    filename_template: str = Field(
        default='{author_name}/{title}.epub',
        description='単独作品のファイル名テンプレート。',
    )
    series_filename_template: str = Field(
        default='{author_name}/{series_title}/{title}.epub',
        description='シリーズ作品のファイル名テンプレート。',
    )
    max_filename_length: int = Field(
        default=50,
        description='ファイル/ディレクトリ名の最大長。長すぎる場合は自動的に切り詰められます。',
    )
    cleanup_after_build: bool = Field(
        default=False,
        description='EPUB生成後に中間ファイル(ワークスペース)を削除するかどうか。',
    )
    default_theme_name: str = Field(
        default='default',
        description='EPUBテーマ(テンプレート)のデフォルト名。',
    )


class PngquantSettings(BaseModel):
    """pngquantによるPNG圧縮の設定。"""

    colors: int = 256
    quality: str = '65-90'
    speed: int = 3
    strip: bool = True


class JpegoptimSettings(BaseModel):
    """jpegoptimによるJPEG圧縮の設定。"""

    max_quality: int = 85
    strip_all: bool = True
    progressive: bool = True
    preserve_timestamp: bool = True


class CwebpSettings(BaseModel):
    """cwebpによるWebP圧縮の設定。"""

    quality: int = 75
    lossless: bool = False
    metadata: str = 'none'


class CompressionSettings(BaseModel):
    """画像圧縮に関する全体設定。"""

    enabled: bool = Field(default=True, description='画像圧縮を有効にするかどうか。')
    skip_if_larger: bool = Field(
        default=True,
        description='圧縮後のファイルサイズが元より大きい場合に圧縮をスキップするかどうか。',
    )
    max_workers: int = Field(
        default=4,
        description='画像圧縮を並列実行する際の最大ワーカー数。',
    )
    pngquant: PngquantSettings = Field(default_factory=PngquantSettings)
    jpegoptim: JpegoptimSettings = Field(default_factory=JpegoptimSettings)
    cwebp: CwebpSettings = Field(default_factory=CwebpSettings)


class WorkspaceSettings(BaseModel):
    """ワークスペースに関する設定。"""

    root_directory: Path = Field(
        default=Path('./.workspace'),
        description='中間ファイルを保存するワークスペースのルートディレクトリ。',
    )


class CliSettings(BaseModel):
    """CLI/GUIエントリーポイントに固有の設定"""

    default_gui_session_path: Path = Field(
        default=Path('./.gui_session'),
        description='GUIモードで使用するブラウザセッションのデフォルトパス。',
    )
    default_env_filename: str = Field(
        default='.env', description='.envファイルのデフォルト名。'
    )


class Settings(BaseSettings):
    """
    アプリケーションの階層的設定管理クラス。
    以下の優先順位で設定を読み込みます:
    1. Pythonコードからの直接初期化
    2. --config で指定されたカスタムTOMLファイル
    3. 環境変数 (例: PIXIV2EPUB_PROVIDERS__PIXIV__REFRESH_TOKEN=...)
    4. .env ファイル
    5. pyproject.toml内の [tool.pixiv2epub] セクション
    6. モデルで定義されたデフォルト値
    """

    providers: ProviderSettings = Field(default_factory=ProviderSettings)
    downloader: DownloaderSettings = Field(default_factory=DownloaderSettings)
    builder: BuilderSettings = Field(default_factory=BuilderSettings)
    compression: CompressionSettings = Field(default_factory=CompressionSettings)
    workspace: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    cli: CliSettings = Field(default_factory=CliSettings)
    log_level: str = 'INFO'

    _config_file: Path | None = None

    def __init__(self, **values: object):
        config_file_path = values.pop('_config_file', None)
        require_auth = values.pop('require_auth', True)
        self._config_file = (
            Path(cast(Path | str, config_file_path)) if config_file_path else None
        )

        try:
            super().__init__(**values)  # type: ignore [arg-type]
        except (ValidationError, ValueError) as e:
            raise SettingsError(f'設定の検証に失敗しました:\n{e}') from e

        if require_auth:
            pixiv_ok = self.providers.pixiv.refresh_token is not None
            fanbox_ok = self.providers.fanbox.sessid is not None

            if not pixiv_ok and not fanbox_ok:
                raise SettingsError(
                    'PixivまたはFanboxの認証情報が見つかりません。'
                    " 'pixiv2epub auth <service>' コマンドを実行するか、"
                    '設定ファイル、.env、または環境変数で設定してください。'
                )

    model_config = SettingsConfigDict(
        env_nested_delimiter='__',
        env_prefix='PIXIV2EPUB_',
        env_file='.env',
        env_file_encoding='utf-8',
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
        # [FIX] `getattr` を使用して `init_data` に安全にアクセス
        config_file_path = getattr(init_settings, 'init_data', {}).get('_config_file')
        if config_file_path and not isinstance(config_file_path, Path):
            config_file_path = Path(config_file_path)

        return (
            init_settings,
            TomlConfigSettingsSource(settings_cls, config_file_path),
            env_settings,
            dotenv_settings,
            PyProjectTomlSource(settings_cls),
        )
