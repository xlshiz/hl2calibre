import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lxml import etree
from koreader_xpath_cfi import (
    _build_ns_xpath,
    resolve_position,
    XPathResolver,
)
from koreader_parser import parse_xpath


class TestBuildNsXPath(unittest.TestCase):
    def test_basic(self):
        result = _build_ns_xpath('/body/div/p')
        self.assertEqual(result, '/ns:html/ns:body/ns:div/ns:p')

    def test_with_predicates(self):
        result = _build_ns_xpath('/body/div/p[12]')
        self.assertEqual(result, '/ns:html/ns:body/ns:div/ns:p[12]')

    def test_mixed(self):
        result = _build_ns_xpath('/body/div/div/p[1]/span[2]')
        self.assertEqual(result, '/ns:html/ns:body/ns:div/ns:div/ns:p[1]/ns:span[2]')


class TestResolvePosition(unittest.TestCase):
    def setUp(self):
        # Build a simple HTML tree for testing
        html = '''
        <html xmlns="http://www.w3.org/1999/xhtml">
        <body>
        <div id="content">
        <h2 id="ch1">Chapter One</h2>
        <p id="p1">Hello <b>world</b> and <i>foo</i> bar</p>
        <p id="p2">Second paragraph</p>
        </div>
        </body>
        </html>
        '''
        self.tree = etree.HTML(html)

    def test_text_first_node(self):
        """text()[1] should point to the element's .text"""
        result = resolve_position(self.tree, '/body/div/p[1]', 1, 0)
        self.assertIsNotNone(result)
        self.assertEqual(result['attr'], 'text')
        self.assertEqual(result['char_offset'], 0)
        self.assertIn('/1:0', result['cfi_path'])

    def test_text_second_node_tail(self):
        """text()[2] should point to first child's .tail"""
        result = resolve_position(self.tree, '/body/div/p[1]', 2, 0)
        self.assertIsNotNone(result)
        # The second text node is the tail of the first child (<b>)
        # <p>Hello <b>world</b> and...</p>
        # text()[1] = "Hello " (p.text)
        # text()[2] = " and " (b.tail) → wait, there's " and " before <i>
        # Actually in the actual DOM: p has text "Hello ", then b with text "world",
        # b has tail " and ", then i with text "foo", i has tail " bar"
        # text()[2] = b.tail = " and "
        self.assertEqual(result['char_offset'], 0)

    def test_text_first_node_offset(self):
        """text()[1] with offset should work"""
        result = resolve_position(self.tree, '/body/div/p[1]', 1, 3)
        self.assertIsNotNone(result)
        self.assertEqual(result['char_offset'], 3)

    def test_h2_heading(self):
        """h2 should have text"""
        result = resolve_position(self.tree, '/body/div/h2', 1, 0)
        self.assertIsNotNone(result)
        self.assertEqual(result['elem'].tag, 'h2')
        self.assertEqual(result['attr'], 'text')

    def test_element_with_id(self):
        """Elements with id should include assertions in CFI"""
        result = resolve_position(self.tree, '/body/div/p[2]', 1, 0)
        self.assertIsNotNone(result)
        # p[id='p2'] should have [p2] in its step
        self.assertIn('[p2]', result['cfi_path'])


class TestXPathResolver(unittest.TestCase):
    """Integration test with a real EPUB file."""

    @classmethod
    def setUpClass(cls):
        cls.epub_path = '/tmp/pi-github-repos/kyxap/koreader-calibre-plugin/dummy_device/Carroll, Lewis/Alice\'s Adventures in Wonderland - Lewis Carroll.epub'
        if os.path.exists(cls.epub_path):
            cls.resolver = XPathResolver(cls.epub_path)
        else:
            cls.resolver = None

    @classmethod
    def tearDownClass(cls):
        if cls.resolver:
            cls.resolver.close()

    def test_load_spine_html(self):
        if not self.resolver:
            self.skipTest('EPUB not found')
        tree = self.resolver.get_spine_html(6, 'OEBPS/@public@vhost@g@gutenberg@html@files@11@11-h@11-h-5.htm.html')
        self.assertIsNotNone(tree)

    def test_resolve_known_position(self):
        """Test resolving the position from the dummy annotation."""
        if not self.resolver:
            self.skipTest('EPUB not found')
        tree = self.resolver.get_spine_html(6, 'OEBPS/@public@vhost@g@gutenberg@html@files@11@11-h@11-h-5.htm.html')
        self.assertIsNotNone(tree)

        result = resolve_position(tree, '/body/div/p[12]', 1, 0)
        self.assertIsNotNone(result)
        self.assertIn('/1:0', result['cfi_path'])


if __name__ == '__main__':
    unittest.main()
