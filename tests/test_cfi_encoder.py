import pytest
from lxml import etree
from cfi_encoder import build_text_map, find_text_in_html, _encode_cfi_path, compute_full_cfi


def _parse(html_str):
    return etree.HTML(html_str)


class TestBuildTextMap:
    def test_simple(self):
        root = _parse('<html><body><p>Hello world</p></body></html>')
        flat_text, node_map = build_text_map(root)
        assert 'Hello world' in flat_text

    def test_returns_tuple(self):
        root = _parse('<html><body><p>Test</p></body></html>')
        result = build_text_map(root)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_node_map_entries(self):
        root = _parse('<html><body><p>Hello</p></body></html>')
        flat_text, node_map = build_text_map(root)
        assert len(node_map) > 0
        elem, attr, start, length = node_map[0]
        assert attr in ('text', 'tail')
        assert isinstance(start, int)
        assert isinstance(length, int)

    def test_skips_comments(self):
        html = '<html><body><!-- comment --><p>Hello</p></body></html>'
        root = _parse(html)
        flat_text, node_map = build_text_map(root)
        assert 'comment' not in flat_text
        assert 'Hello' in flat_text

    def test_tail_text(self):
        html = '<html><body><p>Hello</p>tail text</body></html>'
        root = _parse(html)
        flat_text, node_map = build_text_map(root)
        assert 'tail text' in flat_text


class TestFindTextInHtml:
    def test_find_text_in_flat(self):
        root = _parse('<html><body><p>Hello beautiful world</p></body></html>')
        result = find_text_in_html(root, 'beautiful')
        assert result is not None
        elem, attr, char_offset, cfi_path, end_cfi_path = result
        assert char_offset == 6

    def test_encode_cfi_returns_string(self):
        root = _parse('<html><body><p>Hello world</p></body></html>')
        result = find_text_in_html(root, 'world')
        assert result is not None
        _, _, _, cfi_path, _ = result
        assert cfi_path.startswith('/')

    def test_text_not_found(self):
        root = _parse('<html><body><p>Hello world</p></body></html>')
        result = find_text_in_html(root, 'nonexistent')
        assert result is None

    def test_multinode_text(self):
        html = '<html><body><p>First paragraph.</p><p>Second paragraph.</p></body></html>'
        root = _parse(html)
        result = find_text_in_html(root, 'Second')
        assert result is not None
        elem, attr, char_offset, cfi_path, end_cfi_path = result
        assert char_offset == 0


class TestComputeFullCfi:
    def test_format(self):
        result = compute_full_cfi(0, '/4/2/1:100')
        assert result == 'epubcfi(/6/4!/4/2/1:100)'

    def test_spine_index_calculation(self):
        result = compute_full_cfi(1, '/4/2/1:0')
        assert result == 'epubcfi(/6/8!/4/2/1:0)'
