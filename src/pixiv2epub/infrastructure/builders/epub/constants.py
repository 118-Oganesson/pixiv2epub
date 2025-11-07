# FILE: src/pixiv2epub/infrastructure/builders/epub/constants.py
"""
EPUBファイル構造に関連する定数を集約します。
"""

# EPUBコンテナの必須ファイルとディレクトリ
MIMETYPE_FILE_NAME = 'mimetype'
META_INF_DIR = 'META-INF'
OEBPS_DIR = 'OEBPS'

# EPUB内の主要なXMLファイルとパス
CONTAINER_XML_PATH = f'{META_INF_DIR}/container.xml'
ROOT_FILE_PATH = f'{OEBPS_DIR}/content.opf'
NAV_XHTML_PATH = f'{OEBPS_DIR}/nav.xhtml'

# MIMEタイプ
OEBPS_PACKAGE_MIMETYPE = 'application/oebps-package+xml'
