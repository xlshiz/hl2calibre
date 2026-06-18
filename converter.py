import hashlib
from datetime import datetime, timezone
from typing import Optional

try:
    from .mrexpt_parser import MrexptRecord
except ImportError:
    from mrexpt_parser import MrexptRecord


def make_uuid(book_id: int, seq: int, timestamp_ms: int) -> str:
    raw = f'mrexpt-{book_id}-{seq}-{timestamp_ms}'
    return hashlib.md5(raw.encode()).hexdigest()


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
