# FILE: src/pixiv2epub/infrastructure/providers/strategies/update_checkers.py
import hashlib
import json
from typing import Any, Dict, Tuple

import canonicaljson

from ...models.workspace import Workspace
from .interfaces import IUpdateCheckStrategy


def _extract_critical_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """EPUB生成に不可欠なデータのみを抽出する。"""
    return {
        "title": raw_data.get("title"),
        "seriesId": raw_data.get("seriesId"),
        "seriesTitle": raw_data.get("seriesTitle"),
        "userId": raw_data.get("userId"),
        "coverUrl": raw_data.get("coverUrl"),
        "tags": raw_data.get("tags"),
        "caption": raw_data.get("caption"),
        "text": raw_data.get("text"),
        "illusts": raw_data.get("illusts"),
        "images": raw_data.get("images"),
        "cdate": raw_data.get("cdate"),
    }


def _generate_content_hash(raw_json_data: Dict[str, Any]) -> str:
    """JSON辞書からSHA-256ハッシュを計算する。"""
    critical_data = _extract_critical_data(raw_json_data)
    canonical_bytes = canonicaljson.encode_canonical_json(critical_data)
    return hashlib.sha256(canonical_bytes).hexdigest()


class ContentHashUpdateStrategy(IUpdateCheckStrategy):
    """コンテンツのハッシュ値を比較して更新を判断する戦略。"""

    def is_update_required(
        self, workspace: Workspace, api_response: Dict
    ) -> Tuple[bool, str]:
        new_hash = _generate_content_hash(api_response)
        if not workspace.manifest_path.exists():
            return True, new_hash
        try:
            with open(workspace.manifest_path, "r", encoding="utf-8") as f:
                old_hash = json.load(f).get("content_hash")
            if old_hash and old_hash == new_hash:
                return False, new_hash
        except (json.JSONDecodeError, IOError):
            return True, new_hash
        return True, new_hash


class TimestampUpdateStrategy(IUpdateCheckStrategy):
    """タイムスタンプを比較して更新を判断する戦略。"""

    def __init__(self, timestamp_key: str):
        self.key = timestamp_key

    def is_update_required(
        self, workspace: Workspace, api_response: Dict
    ) -> Tuple[bool, str]:
        new_timestamp = api_response.get(self.key, "")
        if not workspace.manifest_path.exists():
            return True, new_timestamp
        try:
            with open(workspace.manifest_path, "r", encoding="utf-8") as f:
                old_timestamp = json.load(f).get("content_hash")
            if old_timestamp and old_timestamp == new_timestamp:
                return False, new_timestamp
        except (json.JSONDecodeError, IOError):
            return True, new_timestamp
        return True, new_timestamp