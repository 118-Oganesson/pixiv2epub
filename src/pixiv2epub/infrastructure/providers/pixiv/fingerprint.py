# FILE: src/pixiv2epub/providers/pixiv/fingerprint.py
import hashlib
from typing import Any, Dict

import canonicaljson


def extract_critical_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    APIレスポンスからEPUB生成に不可欠なデータのみを抽出・再構築する。
    閲覧数など、EPUBの内容に影響しないノイズデータは除外する。
    """
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


def generate_content_hash(raw_json_data: Dict[str, Any]) -> str:
    """
    生のJSON辞書からセマンティック・フィンガープリントを生成する。

    1. EPUBに影響する重要データを抽出
    2. データを正規化 (Canonical JSON)
    3. SHA-256ハッシュを計算
    """
    critical_data = extract_critical_data(raw_json_data)
    canonical_bytes = canonicaljson.encode_canonical_json(critical_data)
    return hashlib.sha256(canonical_bytes).hexdigest()
