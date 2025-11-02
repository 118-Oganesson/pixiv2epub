# whitelist.py
"""
このファイルは Vulture が検出した「デッドコード」の誤検知を
抑制するためのホワイトリストです。

Pydanticモデルのフィールド、Typerのコールバック、
ABCの抽象メソッド実装など、Vulture が静的解析で
「未使用」と判断してしまう項目をここで定義することで、
Vulture のレポートから除外します。
"""

# 以下の名前は、プロジェクトのどこかで定義されていますが、
# Vultureによって「未使用」と報告されたものです。
# このファイルでこれらの名前を定義することにより、Vultureは
# これらを「使用されている」とみなし、警告を抑制します。

# --- Pydanticモデルのフィールド (domain.py) ---
media_type
properties
# 'model_config' は Pydantic v2 の設定用フィールド
model_config
# 'type_' は Pydantic のエイリアス '@type' のためのフィールド
type_
# 'context_' は Pydantic のエイリアス '@context' のためのフィールド
context_
dateModified
keywords
mainEntityOfPage
mediaType

# --- Pydanticモデルのフィールド (fanbox.py) ---
icon_url
file_id
url_embed_id
thumbnail_url
width
height
size
cover
has_adult_content
profile
html
file_map
url_embed_map
embed_map

# --- Pydanticモデルのフィールド (pixiv.py) ---
like
bookmark
view
small
medium
restrict
x_restrict
sl
visible
available_message
novel_image_id
viewable
viewable_message
caption
cdate
ai_type
is_original
rating
illusts
series_title
series_is_watched

# --- Pydanticモデルのフィールド (workspace.py) ---
created_at_utc
content_etag
workspace_schema_version
provider_specific_data

# # --- 定数 (constants.py) ---
# NAMESPACE_UUID

# # --- 未使用と報告されたメソッド ---
# # (ABCの実装や、動的ディスパッチ、Pydanticバリデーターなど)
# get_builder_name
# empty_list_to_dict
# creator_info
# assign_order_if_missing
# compress_batch

# # --- 未使用と報告された関数 (Typerコールバック) ---
# gui
# main_callback