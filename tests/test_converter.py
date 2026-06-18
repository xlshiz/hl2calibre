from mrexpt_parser import MrexptRecord
from converter import convert_record, make_uuid


def _make_record(**kwargs):
    defaults = dict(
        seq=26,
        title='Test Book',
        file_path='ch01.xhtml',
        file_path_lower='ch01.xhtml',
        chapter=52,
        unknown1=0,
        offset=483,
        length=100,
        color_code=-65536,
        timestamp_ms=1671754358620,
        unknown_flag='',
        note='',
        _highlighted_text='Some text',
        flag1=0,
        flag2=0,
        flag3=0,
    )
    defaults.update(kwargs)
    return MrexptRecord(**defaults)


def test_convert_basic():
    record = _make_record()
    result = convert_record(record, spine_index=52, book_id=123)
    assert result['type'] == 'highlight'
    assert result['highlighted_text'] == 'Some text'
    assert 'T' in result['timestamp'] and '+' in result['timestamp']
    assert result['spine_index'] == 52
    assert result['toc_family_titles'] == ('Chapter 52',)
    assert result['pos_type'] == 'epubcfi'


def test_convert_with_note():
    record = _make_record(note='My note')
    result = convert_record(record, spine_index=1, book_id=1)
    assert result['notes'] == 'My note'


def test_convert_color():
    record = _make_record(color_code=-65536)
    result = convert_record(record, spine_index=0, book_id=1)
    assert result['style']['which'] == 'red'
    assert result['style']['kind'] == 'color'
    # light/dark removed to match native Calibre annotation style format
    assert 'light' not in result['style']
    assert 'dark' not in result['style']


def test_convert_br_replacement():
    record = _make_record(_highlighted_text='Line1<BR>Line2')
    result = convert_record(record, spine_index=0, book_id=1)
    assert '\n' in result['highlighted_text']
    assert '<BR>' not in result['highlighted_text']


def test_make_uuid_deterministic():
    uuid1 = make_uuid(book_id=123, seq=26, timestamp_ms=1671754358620)
    uuid2 = make_uuid(book_id=123, seq=26, timestamp_ms=1671754358620)
    assert uuid1 == uuid2


def test_make_uuid_unique():
    uuid1 = make_uuid(book_id=123, seq=26, timestamp_ms=1671754358620)
    uuid2 = make_uuid(book_id=123, seq=27, timestamp_ms=1671754358620)
    assert uuid1 != uuid2


def test_convert_without_cfi():
    record = _make_record()
    result = convert_record(record, spine_index=52, cfi_path=None, book_id=123)
    assert 'start_cfi' not in result


def test_convert_with_cfi():
    record = _make_record()
    result = convert_record(record, spine_index=52, cfi_path='/4/2/1:483', book_id=123)
    assert result['start_cfi'] == '/4/2/1:483'
    assert result['end_cfi'] == '/4/2/1:483'
