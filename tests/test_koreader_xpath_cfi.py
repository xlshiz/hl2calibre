import sys
import os
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lxml import etree
from koreader_xpath_cfi import (
    _build_ns_xpath,
    resolve_position,
    resolve_annotation_position,
    XPathResolver,
)
from koreader_parser import parse_xpath, KoreaderAnnotation


# ── Minimal XHTML content for testing ──────────────────────────────────────

SPINE_0_HTML = b"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Chapter 1</title></head>
<body>
<div id="content">
<h2 id="ch1">Chapter One</h2>
<p id="p1">Hello <b>world</b> and <i>foo</i> bar</p>
<p id="p2">Second paragraph with <b>bold</b> text</p>
<p id="p3">Third <span id="s1">span text</span> and more</p>
</div>
</body>
</html>
"""

SPINE_1_HTML = b"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Chapter 2</title></head>
<body>
<div id="content">
<h2 id="ch2">Chapter Two</h2>
<p id="p1">Some text in chapter two</p>
<p id="p2">More text <em>emphasized</em> here</p>
</div>
</body>
</html>
"""


def _create_test_epub():
    """Create a minimal EPUB zip in a temp file and return the path."""
    tmp = tempfile.NamedTemporaryFile(suffix='.epub', delete=False)
    tmp.close()
    with zipfile.ZipFile(tmp.name, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('OEBPS/Text/chapter01.xhtml', SPINE_0_HTML)
        zf.writestr('OEBPS/Text/chapter02.xhtml', SPINE_1_HTML)
        # Also read from zip returns bytes, which lxml.HTML accepts
        # Minimal OPF
        opf_content = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="3.0">
  <metadata>
    <dc:identifier id="bookid" xmlns:dc="http://purl.org/dc/elements/1.1/">test-book</dc:identifier>
    <dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Test Book</dc:title>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="ch1" href="OEBPS/Text/chapter01.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch2" href="OEBPS/Text/chapter02.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="ch1"/>
    <itemref idref="ch2"/>
  </spine>
</package>"""
        zf.writestr('OEBPS/package.opf', opf_content)
    return tmp.name


# ═══════════════════════════════════════════════════════════════════════════
# Test cases
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildNsXPath(unittest.TestCase):
    """_build_ns_xpath: test XHTML namespace prefix injection."""

    def test_basic(self):
        result = _build_ns_xpath('/body/div/p')
        self.assertEqual(result, '/ns:html/ns:body/ns:div/ns:p')

    def test_with_predicates(self):
        result = _build_ns_xpath('/body/div/p[12]')
        self.assertEqual(result, '/ns:html/ns:body/ns:div/ns:p[12]')

    def test_mixed(self):
        result = _build_ns_xpath('/body/div/div/p[1]/span[2]')
        self.assertEqual(result, '/ns:html/ns:body/ns:div/ns:div/ns:p[1]/ns:span[2]')

    def test_deep_nesting(self):
        result = _build_ns_xpath('/body/section/article/div/p/a')
        self.assertEqual(result, '/ns:html/ns:body/ns:section/ns:article/ns:div/ns:p/ns:a')


class TestResolvePosition(unittest.TestCase):
    """resolve_position: test XPath-to-CFI conversion on inline HTML."""

    @classmethod
    def setUpClass(cls):
        cls.tree = etree.HTML(SPINE_0_HTML)

    def test_text_first_node(self):
        """text()[1] = element.text with offset 0"""
        result = resolve_position(self.tree, '/body/div/p[1]', 1, 0)
        self.assertIsNotNone(result)
        self.assertEqual(result['attr'], 'text')
        self.assertEqual(result['char_offset'], 0)
        self.assertIn('/1:0', result['cfi_path'])

    def test_text_first_node_offset(self):
        """text()[1] with non-zero offset"""
        result = resolve_position(self.tree, '/body/div/p[1]', 1, 3)
        self.assertIsNotNone(result)
        self.assertEqual(result['char_offset'], 3)

    def test_h2_heading(self):
        """h2 text node should resolve correctly"""
        result = resolve_position(self.tree, '/body/div/h2', 1, 0)
        self.assertIsNotNone(result)
        # etree.HTML() strips XHTML namespace, tag is just 'h2'
        self.assertIn(result['elem'].tag, ('h2', '{http://www.w3.org/1999/xhtml}h2'))
        self.assertEqual(result['attr'], 'text')

    def test_element_with_id(self):
        """Elements with id should produce CFI with id assertions"""
        result = resolve_position(self.tree, '/body/div/p[2]', 1, 0)
        self.assertIsNotNone(result)
        # p[id='p2'] should have [p2] assertion in its step
        self.assertIn('[p2]', result['cfi_path'],
                      f'CFI {result["cfi_path"]} should contain [p2] assertion')

    def test_second_text_node_tail(self):
        """text()[2] should resolve to first child's tail"""
        result = resolve_position(self.tree, '/body/div/p[1]', 2, 0)
        self.assertIsNotNone(result)
        # <p>Hello <b>world</b> and <i>foo</i> bar</p>
        # text()[1] = "Hello " (p.text)
        # text()[2] = " and " (b.tail) with offset
        self.assertEqual(result['char_offset'], 0)

    def test_third_text_node_tail(self):
        """text()[3] should resolve to second child's tail"""
        result = resolve_position(self.tree, '/body/div/p[1]', 3, 0)
        self.assertIsNotNone(result)
        # text()[3] = " bar" (i.tail)
        self.assertEqual(result['char_offset'], 0)

    def test_cfi_format(self):
        """CFI path should end with /N:offset format"""
        result = resolve_position(self.tree, '/body/div/p[1]', 1, 0)
        self.assertIsNotNone(result)
        self.assertRegex(result['cfi_path'], r'/\d+:\d+$')

    def test_spine_offset_preserved(self):
        """char_offset should be preserved in the final CFI"""
        result = resolve_position(self.tree, '/body/div/p[2]', 1, 5)
        self.assertIsNotNone(result)
        self.assertIn(':5', result['cfi_path'])


class TestXPathResolver(unittest.TestCase):
    """Integration tests with a real (minimal) EPUB zip."""

    @classmethod
    def setUpClass(cls):
        cls.epub_path = _create_test_epub()
        cls.resolver = XPathResolver(cls.epub_path)

    @classmethod
    def tearDownClass(cls):
        cls.resolver.close()
        os.unlink(cls.epub_path)

    def test_load_spine_html(self):
        """get_spine_html should load valid HTML from EPUB"""
        tree = self.resolver.get_spine_html(0, 'OEBPS/Text/chapter01.xhtml')
        self.assertIsNotNone(tree)
        root = tree
        self.assertIn('Chapter One', etree.tostring(root, encoding='unicode'))

    def test_load_second_spine(self):
        """get_spine_html should load different spine files"""
        tree = self.resolver.get_spine_html(1, 'OEBPS/Text/chapter02.xhtml')
        self.assertIsNotNone(tree)
        self.assertIn('Chapter Two', etree.tostring(tree, encoding='unicode'))

    def test_load_nonexistent_spine(self):
        """get_spine_html should return None for missing files"""
        tree = self.resolver.get_spine_html(0, 'nonexistent.html')
        self.assertIsNone(tree)

    def test_resolve_simple_position(self):
        """Resolve a known position: first paragraph, first text node"""
        tree = self.resolver.get_spine_html(0, 'OEBPS/Text/chapter01.xhtml')
        self.assertIsNotNone(tree)
        result = resolve_position(tree, '/body/div/p[1]', 1, 0)
        self.assertIsNotNone(result)
        self.assertIn('/1:0', result['cfi_path'])

    def test_resolve_position_with_id_assertion(self):
        """Resolve a position on an element with id attribute"""
        tree = self.resolver.get_spine_html(0, 'OEBPS/Text/chapter01.xhtml')
        self.assertIsNotNone(tree)
        result = resolve_position(tree, '/body/div/p[2]', 1, 0)
        self.assertIsNotNone(result)
        self.assertIn('[p2]', result['cfi_path'],
                      f'Expected [p2] in {result["cfi_path"]}')

    def test_resolve_annotation(self):
        """End-to-end: resolve_annotation_position for a KOReader annotation"""
        tree = self.resolver.get_spine_html(0, 'OEBPS/Text/chapter01.xhtml')
        self.assertIsNotNone(tree)

        annot = KoreaderAnnotation(
            text='Hello world',
            pos0='/body/DocFragment[1]/body/div/p[1]/text().0',
            pos1='/body/DocFragment[1]/body/div/p[1]/text().11',
            chapter='Chapter 1',
            datetime_str='2020-11-16 18:00:00',
            drawer='lighten',
            color='yellow',
        )

        start_cfi, end_cfi = resolve_annotation_position(tree, annot)
        self.assertIsNotNone(start_cfi)
        self.assertIsNotNone(end_cfi)
        self.assertNotEqual(start_cfi, end_cfi)
        self.assertIn('/1:0', start_cfi)
        self.assertIn('/1:11', end_cfi)

    def test_resolve_annotation_cross_spine_filtered(self):
        """Annotation with pos0/pos1 in different DocFragments: pos1 is on different spine"""
        # For cross-spine, the importer.py filters them before calling resolver.
        # Here we just ensure resolve_annotation_position handles same-spine cases.
        tree = self.resolver.get_spine_html(1, 'OEBPS/Text/chapter02.xhtml')
        self.assertIsNotNone(tree)

        annot = KoreaderAnnotation(
            text='emphasized',
            pos0='/body/DocFragment[2]/body/div/p[2]/text().0',
            pos1='/body/DocFragment[2]/body/div/p[2]/text().11',
            chapter='Chapter 2',
            datetime_str='2020-11-16 19:00:00',
            drawer='underscore',
        )

        start_cfi, end_cfi = resolve_annotation_position(tree, annot)
        self.assertIsNotNone(start_cfi)

    def test_resolve_nonexistent_position(self):
        """Resolving a position that doesn't exist should return None"""
        tree = self.resolver.get_spine_html(0, 'OEBPS/Text/chapter01.xhtml')
        self.assertIsNotNone(tree)
        result = resolve_position(tree, '/body/div/notexist', 1, 0)
        self.assertIsNone(result)

    def test_cache_hits(self):
        """Multiple loads of the same spine should return the same tree"""
        t1 = self.resolver.get_spine_html(0, 'OEBPS/Text/chapter01.xhtml')
        t2 = self.resolver.get_spine_html(0, 'OEBPS/Text/chapter01.xhtml')
        self.assertIs(t1, t2)  # Same object from cache


if __name__ == '__main__':
    unittest.main()
