# src/pixiv2epub/utils/url_parser.py
from ..shared.constants import PATTERNS
from ..shared.enums import ContentType, Provider
from ..shared.exceptions import InvalidInputError

URL_PATTERNS = {
    (Provider.PIXIV, ContentType.WORK): PATTERNS.PIXIV_WORK,
    (Provider.PIXIV, ContentType.SERIES): PATTERNS.PIXIV_SERIES,
    (Provider.PIXIV, ContentType.CREATOR): PATTERNS.PIXIV_CREATOR,
    (Provider.FANBOX, ContentType.WORK): PATTERNS.FANBOX_WORK,
    (Provider.FANBOX, ContentType.CREATOR): PATTERNS.FANBOX_CREATOR,
}


def parse_content_identifier(
    input_str: str,
) -> tuple[Provider, ContentType, int | str]:
    """
    入力された文字列 (URL) を解析し、対象のProvider、ContentType、およびIDを返します。
    どのパターンにも一致しない場合は InvalidInputError を送出します。
    """
    for (provider, content_type), pattern in URL_PATTERNS.items():
        if match := pattern.search(input_str):
            # fanbox_creatorは2つのキャプチャグループを持つため、Noneでない最初のグループを取得
            if provider == Provider.FANBOX and content_type == ContentType.CREATOR:
                if target_id := next(
                    (g for g in match.groups() if g is not None), None
                ):
                    return provider, content_type, target_id
            # その他のパターンは最初のキャプチャグループを取得
            else:
                target_id_str = match.group(1)
                try:
                    target_id_int = int(target_id_str)
                    return provider, content_type, target_id_int
                except (ValueError, TypeError):
                    return provider, content_type, target_id_str

    raise InvalidInputError(f"対応していない、または無効なURL形式です: '{input_str}'")
