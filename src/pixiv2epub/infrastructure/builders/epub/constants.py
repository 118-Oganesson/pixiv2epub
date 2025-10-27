# FILE: src/pixiv2epub/infrastructure/builders/epub/constants.py
"""
EPUBファイル構造に関連する定数を集約します。
"""

# EPUBコンテナの必須ファイルとディレクトリ
MIMETYPE_FILE_NAME = "mimetype"
META_INF_DIR = "META-INF"
OEBPS_DIR = "OEBPS"

# EPUB内の主要なXMLファイルとパス
CONTAINER_XML_PATH = f"{META_INF_DIR}/container.xml"
ROOT_FILE_PATH = f"{OEBPS_DIR}/content.opf"
NAV_XHTML_PATH = f"{OEBPS_DIR}/nav.xhtml"

# MIMEタイプ
MIMETYPE_STRING = "application/epub+zip"
OEBPS_PACKAGE_MIMETYPE = "application/oebps-package+xml"

# container.xml のテンプレート
# このファイルは固定なので、テンプレートエンジンを使わず定数として定義します。
CONTAINER_XML_CONTENT = f"""<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="{ROOT_FILE_PATH}" media-type="{OEBPS_PACKAGE_MIMETYPE}"/>
  </rootfiles>
</container>
""".encode()
