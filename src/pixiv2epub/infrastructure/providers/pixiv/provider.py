# FILE: src/pixiv2epub/infrastructure/providers/pixiv/provider.py
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import canonicaljson
from loguru import logger
from pixivpy3 import PixivError
from pydantic import ValidationError

from ....domain.interfaces import IProvider, IWorkspaceRepository
from ....models.domain import UnifiedContentManifest
from ....models.pixiv import NovelApiResponse, NovelSeriesApiResponse
from ....models.workspace import Workspace, WorkspaceManifest
from ....shared.constants import WORKSPACE_PATHS
from ....shared.enums import ContentType
from ....shared.exceptions import ApiError, DataProcessingError, ProviderError
from ....shared.settings import Settings
from ...strategies.mappers import PixivMetadataMapper
from ...strategies.parsers import PixivTagParser
from .client import PixivApiClient
from .constants import PIXIV_EPOCH
from .downloader import ImageDownloader as PixivImageDownloader


def _extract_critical_data_for_hash(raw_data: dict[str, Any]) -> dict[str, Any]:
    """EPUB生成に不可欠なデータのみを抽出する。"""
    # この関数はハッシュ計算に使用されるため、キー名はAPIレスポンスのままとする
    return {
        'title': raw_data.get('title'),
        'seriesId': raw_data.get('seriesId'),
        'seriesTitle': raw_data.get('seriesTitle'),
        'userId': raw_data.get('userId'),
        'coverUrl': raw_data.get('coverUrl'),
        'tags': raw_data.get('tags'),
        'caption': raw_data.get('caption'),
        'text': raw_data.get('text'),
        'illusts': raw_data.get('illusts'),
        'images': raw_data.get('images'),
        'cdate': raw_data.get('cdate'),
    }


def _generate_content_hash(raw_json_data: dict[str, Any]) -> str:
    """JSON辞書からSHA-256ハッシュを計算する。"""
    critical_data = _extract_critical_data_for_hash(raw_json_data)
    canonical_bytes = canonicaljson.encode_canonical_json(critical_data)
    return hashlib.sha256(canonical_bytes).hexdigest()


class PixivProvider(IProvider):
    """
    Pixivから小説データを取得するための、自己完結した高性能プロバイダ。
    """

    def __init__(
        self,
        settings: Settings,
        api_client: PixivApiClient,
        repository: IWorkspaceRepository,
    ):
        self.settings = settings
        self.api_client = api_client
        self.repository = repository

        # 内部で利用するコンポーネントをインスタンス化
        self._downloader = PixivImageDownloader(
            api_client=self.api_client,
            overwrite=self.settings.downloader.overwrite_existing_images,
        )
        self._parser = PixivTagParser()
        self._mapper = PixivMetadataMapper()

    @classmethod
    def get_provider_name(cls) -> str:
        return 'pixiv'

    def get_works(
        self, identifier: int | str, content_type: ContentType
    ) -> list[Workspace]:
        """
        IProviderインターフェースの統一エントリーポイント。
        コンテンツ種別に応じて適切な内部メソッドに処理を委譲します。
        """
        try:
            if content_type == ContentType.WORK:
                workspace = self._get_single_work(int(identifier))
                return [workspace] if workspace else []
            elif content_type == ContentType.SERIES:
                return self._get_multiple_works(int(identifier))
            elif content_type == ContentType.CREATOR:
                return self._get_creator_works(int(identifier))
            else:
                raise ProviderError(
                    f'Pixiv provider does not support content type: {content_type.name}',
                    self.get_provider_name(),
                )
        except (ApiError, DataProcessingError) as e:
            # 処理中のエラーを捕捉し、Orchestratorに伝播させる
            logger.error(f'処理に失敗しました: {e}')
            raise
        except Exception as e:
            # f-string 補間を避ける
            logger.error('予期せぬエラーが発生しました。', exc_info=True)
            raise ProviderError(f'予期せぬエラー: {e}', self.get_provider_name()) from e

    def _get_single_work(self, novel_id: int) -> Workspace | None:
        """
        単一の小説を取得し、Workspaceを生成します。
        ハッシュチェックを行い、更新がある場合のみ詳細データを取得・処理します。
        """

        # 1. ハッシュチェック用の基本データ(webview)をまず取得
        raw_webview_novel_data = self.api_client.webview_novel(novel_id)

        # 2. 事前更新チェック
        workspace_path = self.repository.get_workspace_path(
            novel_id, self.get_provider_name()
        )
        manifest_path = workspace_path / WORKSPACE_PATHS.MANIFEST_FILE_NAME

        update_required, new_hash = self._perform_hash_check(
            manifest_path, raw_webview_novel_data
        )

        if not update_required:
            logger.bind(
                provider=self.get_provider_name(),
                identifier=novel_id,
                content_type=ContentType.WORK.name,
            ).info('コンテンツに変更なし、スキップします。')
            return None

        # 3. 更新がある場合のみ、詳細データ取得とワークスペースセットアップを実行
        logger.bind(
            provider=self.get_provider_name(),
            identifier=novel_id,
            content_type=ContentType.WORK.name,
        ).info('コンテンツの更新を検出、処理を続行します。')
        raw_novel_detail_data = self.api_client.novel_detail(novel_id)

        workspace = self.repository.setup_workspace(novel_id, self.get_provider_name())
        if workspace.source_path.exists():
            shutil.rmtree(workspace.source_path)
        workspace.source_path.mkdir(parents=True, exist_ok=True)

        # 4. ワークスペースにコンテンツを処理・格納
        fetched_data: dict[str, dict[str, Any]] = {
            'primary_data': raw_webview_novel_data,
            'secondary_data': raw_novel_detail_data,
        }
        metadata = self._process_and_populate_workspace(workspace, fetched_data)

        # 5. メタデータとマニフェストを永続化
        source_identifier = f'tag:pixiv.net,{PIXIV_EPOCH}:novel:{novel_id}'

        manifest = WorkspaceManifest(
            provider_name=self.get_provider_name(),
            created_at_utc=datetime.now(UTC).isoformat(),
            source_identifier=source_identifier,
            content_etag=new_hash,
            workspace_schema_version='1.0',
        )
        self.repository.persist_metadata(workspace, metadata, manifest)

        logger.bind(title=metadata.core.name).success(
            '作品データの処理が完了しました。'
        )
        return workspace

    def _get_multiple_works(self, series_id: int) -> list[Workspace]:
        """シリーズ作品をダウンロードし、ビルドします。"""
        logger.info('シリーズの処理を開始')
        series_data = self.get_series_info(series_id)
        novel_ids = [novel.id for novel in series_data.novels]

        if not novel_ids:
            logger.info('ダウンロード対象が見つからず処理を終了します。')
            return []

        downloaded_workspaces = []
        total = len(novel_ids)
        logger.bind(total_novels=total).info('シリーズ内の小説ダウンロードを開始')

        for i, novel_id in enumerate(novel_ids, 1):
            log = logger.bind(current=i, total=total, novel_id=novel_id)
            log.info('--- 小説を処理中 ---')
            try:
                workspace = self._get_single_work(novel_id)
                if workspace:
                    downloaded_workspaces.append(workspace)
            except Exception as e:
                log.bind(error=str(e)).error(
                    '小説のダウンロードに失敗しました。',
                    exc_info=self.settings.log_level == 'DEBUG',
                )

        logger.bind(series_title=series_data.novel_series_detail.title).info(
            'シリーズのダウンロード完了'
        )
        return downloaded_workspaces

    def _get_creator_works(self, user_id: int) -> list[Workspace]:
        """クリエイターの全作品をダウンロードし、ビルドします。"""
        logger.info('ユーザーの全作品の処理を開始')
        single_ids, series_ids = self._fetch_all_user_novel_ids(user_id)

        logger.bind(
            series_count=len(series_ids), single_work_count=len(single_ids)
        ).info('ユーザー作品の取得結果')

        downloaded_workspaces = []
        if series_ids:
            logger.info('--- シリーズ作品の処理を開始 ---')
            for i, s_id in enumerate(series_ids, 1):
                log = logger.bind(current_series=i, total_series=len(series_ids))
                log.info(f'--- シリーズ {s_id} を処理中 ---')
                try:
                    workspaces = self._get_multiple_works(s_id)
                    downloaded_workspaces.extend(workspaces)
                except Exception as e:
                    log.bind(series_id=s_id, error=str(e)).error(
                        'シリーズの処理中にエラーが発生しました。',
                        exc_info=self.settings.log_level == 'DEBUG',
                    )

        if single_ids:
            logger.info('--- 単独作品の処理を開始 ---')
            for i, n_id in enumerate(single_ids, 1):
                log = logger.bind(current_work=i, total_works=len(single_ids))
                log.info(f'--- 単独作品 {n_id} を処理中 ---')
                try:
                    workspace = self._get_single_work(n_id)
                    if workspace:
                        downloaded_workspaces.append(workspace)
                except Exception as e:
                    log.bind(novel_id=n_id, error=str(e)).error(
                        '小説の処理中にエラーが発生しました。',
                        exc_info=self.settings.log_level == 'DEBUG',
                    )

        return downloaded_workspaces

    def _perform_hash_check(
        self,
        manifest_path: Path,
        api_response: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        コンテンツのハッシュ値を比較して更新を判断します。
        """
        new_hash = _generate_content_hash(api_response)
        if not manifest_path.is_file():
            return True, new_hash
        try:
            with open(manifest_path, encoding='utf-8') as f:
                old_hash = json.load(f).get('content_etag')
            if old_hash and old_hash == new_hash:
                return False, new_hash
        except (OSError, json.JSONDecodeError):
            return True, new_hash
        return True, new_hash

    def _process_and_populate_workspace(
        self,
        workspace: Workspace,
        fetched_data: dict[str, dict[str, Any]],
    ) -> UnifiedContentManifest:
        """
        コンテンツをパースし、画像をダウンロードし、XHTMLを保存し、
        最終的なメタデータ(UCM)を生成して返します。
        """
        raw_webview_novel_data = fetched_data['primary_data']
        raw_novel_detail_data = fetched_data['secondary_data']

        # 1. アセットのダウンロード
        image_dir = workspace.assets_path / WORKSPACE_PATHS.IMAGES_DIR_NAME
        cover_path = self._downloader.download_cover(
            raw_novel_detail_data.get('novel', {}), image_dir=image_dir
        )

        # 2. コンテンツの解析と保存
        novel_data = NovelApiResponse.model_validate(raw_webview_novel_data)

        image_paths = self._downloader.download_embedded_images(
            novel_data, image_dir=image_dir
        )

        parsed_text = self._parser.parse(novel_data.text, image_paths)
        pages = parsed_text.split('[newpage]')
        for i, page_content in enumerate(pages):
            filename = workspace.source_path / f'page-{i + 1}.xhtml'
            try:
                filename.write_text(page_content, encoding='utf-8')
            except OSError as e:
                logger.bind(page=i + 1, error=str(e)).error(
                    'ページの保存に失敗しました。'
                )
        logger.bind(page_count=len(pages)).debug('ページの保存が完了しました。')

        # 3. メタデータのマッピング
        parsed_description = self._parser.parse(
            raw_novel_detail_data.get('novel', {}).get('caption', ''), image_paths
        )

        # マッパーが UCM を返す
        metadata = self._mapper.map_to_metadata(
            workspace=workspace,
            cover_path=cover_path,
            novel_data=novel_data,
            detail_data=raw_novel_detail_data,
            parsed_text=parsed_text,
            parsed_description=parsed_description,
            image_paths=image_paths,
        )
        return metadata

    # --- Pixiv固有のヘルパーメソッド ---

    def get_series_info(self, series_id: int | str) -> NovelSeriesApiResponse:
        """シリーズ詳細情報を取得します。"""
        try:
            series_data_dict = self.api_client.novel_series(int(series_id))
            return NovelSeriesApiResponse.model_validate(series_data_dict)
        except (PixivError, ValidationError) as e:
            raise ApiError(
                f'シリーズID {series_id} のメタデータ取得に失敗: {e}',
                self.get_provider_name(),
            ) from e

    def _fetch_all_user_novel_ids(self, user_id: int) -> tuple[list[int], list[int]]:
        """指定されたユーザーの全小説IDを取得し、単独作品とシリーズ作品IDに分離します。"""
        single_ids: list[int] = []
        series_ids: set[int] = set()
        next_url: str | None = None
        while True:
            res = self.api_client.user_novels(user_id, next_url)
            for novel in res.get('novels', []):
                if novel.get('series') and novel['series'].get('id'):
                    series_ids.add(novel['series']['id'])
                else:
                    single_ids.append(novel['id'])
            if not (next_url := res.get('next_url')):
                break
        return single_ids, list(series_ids)
