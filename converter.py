import hashlib
from datetime import datetime, timezone
from typing import Optional

try:
    from .mrexpt_parser import MrexptRecord
    from .koreader_parser import KoreaderAnnotation
    from .koreader_parser import parse_timestamp as koreader_parse_ts
except ImportError:
    from mrexpt_parser import MrexptRecord
    from koreader_parser import KoreaderAnnotation
    from koreader_parser import parse_timestamp as koreader_parse_ts


def make_uuid(book_id: int, seq: int, timestamp_ms: int) -> str:
    raw = f'mrexpt-{book_id}-{seq}-{timestamp_ms}'
    return hashlib.md5(raw.encode()).hexdigest()


def make_koreader_uuid(book_id: int, idx: int, pos0: str, text: str) -> str:
    raw = f'koreader-{book_id}-{idx}-{pos0}-{text[:50]}'
    return hashlib.md5(raw.encode()).hexdigest()


# KOReader drawer type → Calibre builtin style mapping
_KOREADER_DRAWER_MAP = {
    'lighten':    ('color', 'yellow'),
    'underscore': ('decoration', 'wavy'),
    'strikeout':  ('decoration', 'strikeout'),
    'invert':     ('decoration', 'strikeout'),
}

# KOReader color → Calibre builtin color name
_KOREADER_COLOR_MAP = {
    'red':    'red',
    'orange': 'yellow',
    'yellow': 'yellow',
    'green':  'green',
    'olive':  'green',
    'cyan':   'blue',
    'blue':   'blue',
    'purple': 'purple',
    'gray':   'yellow',
    'pink':   'red',
}


def koreader_style_to_calibre(annotation: KoreaderAnnotation) -> dict:
    """将 KOReader 标注样式转为 Calibre 样式字典。"""
    drawer = annotation.drawer or 'lighten'
    color = annotation.color
    kind, which = _KOREADER_DRAWER_MAP.get(drawer, ('color', 'yellow'))

    if kind == 'color' and color and color in _KOREADER_COLOR_MAP:
        which = _KOREADER_COLOR_MAP[color]

    return {
        'type': 'builtin',
        'kind': kind,
        'which': which,
    }


def convert_record(
    record: MrexptRecord,
    spine_index: int,
    cfi_path: Optional[str] = None,
    end_cfi_path: Optional[str] = None,
    spine_name: Optional[str] = None,
    book_id: int = 0,
) -> dict:
    result = {
        'type': 'highlight',
        'uuid': make_uuid(book_id, record.seq, record.timestamp_ms),
        'highlighted_text': record.highlighted_text,
        'notes': record.note,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'spine_index': spine_index,
        'toc_family_titles': (f'Chapter {record.chapter}',),
        'style': {
            'type': 'builtin',
            'kind': 'color',
            'which': record.color_name,
        },
        'pos_type': 'epubcfi',
    }
    if spine_name:
        result['spine_name'] = spine_name
    if cfi_path is not None:
        result['start_cfi'] = cfi_path
        if end_cfi_path is not None:
            result['end_cfi'] = end_cfi_path
        else:
            result['end_cfi'] = cfi_path
    return result


def convert_koreader_record(
    annotation: KoreaderAnnotation,
    idx: int,
    spine_index: int,
    spine_name: str,
    book_id: int,
    start_cfi: str = None,
    end_cfi: str = None,
) -> dict:
    """将 KOReader 标注转为 Calibre 注释格式。"""
    # 使用导入的当前时间作为时间戳，确保 merge 时不会因 removed 记录的
    # 时间戳较新而被丢弃。原始 KOReader 时间保留在 notes 中供参考。
    timestamp = datetime.now(timezone.utc).isoformat()

    result = {
        'type': 'highlight',
        'uuid': make_koreader_uuid(book_id, idx, annotation.pos0, annotation.text),
        'highlighted_text': annotation.text,
        'notes': annotation.notes,
        'timestamp': timestamp,
        'spine_index': spine_index,
        'spine_name': spine_name,
        'toc_family_titles': (annotation.chapter or f'Chapter {spine_index}',),
        'style': koreader_style_to_calibre(annotation),
        'pos_type': 'epubcfi',
    }
    if start_cfi is not None:
        result['start_cfi'] = start_cfi
        result['end_cfi'] = end_cfi if end_cfi is not None else start_cfi
    return result
