#!/bin/bash
set -e
PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="${PLUGIN_DIR}/hl2calibre.zip"
cd "$PLUGIN_DIR"
rm -f "$OUTPUT"
zip -r "$OUTPUT" \
    __init__.py \
    plugin-import-name-hl2calibre.txt \
    action.py \
    mrexpt_parser.py \
    book_matcher.py \
    cfi_encoder.py \
    converter.py \
    importer.py \
    ui.py \
    images/ \
    -x '*.pyc' '__pycache__/*'
echo "插件已打包: $OUTPUT"
