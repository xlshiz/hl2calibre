import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from koreader_parser import (
    parse_sidecar_lua,
    parse_xpath,
    parse_timestamp,
    KoreaderAnnotation,
)

SIDECAR_PATH = '/tmp/pi-github-repos/kyxap/koreader-calibre-plugin/dummy_device/Carroll, Lewis/Alice\'s Adventures in Wonderland - Lewis Carroll.sdr/metadata.epub.lua'


class TestKoreaderXPathParser(unittest.TestCase):
    def test_simple_xpath(self):
        result = parse_xpath('/body/DocFragment[7]/body/div/p[12]/text()[1].0')
        self.assertIsNotNone(result)
        self.assertEqual(result['spine_index'], 6)
        self.assertEqual(result['xpath_within'], '/body/div/p[12]')
        self.assertEqual(result['text_index'], 1)
        self.assertEqual(result['char_offset'], 0)

    def test_second_text_node(self):
        result = parse_xpath('/body/DocFragment[7]/body/div/p[12]/text()[2].1')
        self.assertIsNotNone(result)
        self.assertEqual(result['spine_index'], 6)
        self.assertEqual(result['xpath_within'], '/body/div/p[12]')
        self.assertEqual(result['text_index'], 2)
        self.assertEqual(result['char_offset'], 1)

    def test_later_spine(self):
        result = parse_xpath('/body/DocFragment[9]/body/div/h2/text()[1].0')
        self.assertIsNotNone(result)
        self.assertEqual(result['spine_index'], 8)
        self.assertEqual(result['xpath_within'], '/body/div/h2')
        self.assertEqual(result['text_index'], 1)
        self.assertEqual(result['char_offset'], 0)

    def test_invalid_xpath(self):
        self.assertIsNone(parse_xpath(''))
        self.assertIsNone(parse_xpath('not/a/path'))
        self.assertIsNone(parse_xpath('/body/div/p/text()'))


class TestTimestampParser(unittest.TestCase):
    def test_valid_timestamp(self):
        ts = parse_timestamp('2020-11-16 18:50:53')
        self.assertIsNotNone(ts)
        # 2020-11-16 18:50:53 UTC = 1605552653000 ms
        self.assertEqual(ts, 1605552653000)

    def test_empty_timestamp(self):
        self.assertIsNone(parse_timestamp(''))
        self.assertIsNone(parse_timestamp(None))

    def test_invalid_format(self):
        self.assertIsNone(parse_timestamp('2020/11/16'))


class TestSidecarParser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.path.exists(SIDECAR_PATH):
            cls.records = parse_sidecar_lua(SIDECAR_PATH)
        else:
            cls.records = []

    def test_parse_with_positions(self):
        """All returned annotations should have valid pos0/pos1."""
        self.assertGreater(len(self.records), 0, 'No records parsed')
        for r in self.records:
            self.assertTrue(bool(r.pos0), f'Annotation missing pos0')
            self.assertTrue(bool(r.pos1), f'Annotation missing pos1')

    def test_spine_indices_valid(self):
        self.assertGreater(len(self.records), 0, 'No records parsed')
        for r in self.records:
            self.assertIsNotNone(r.spine_index)
            self.assertGreaterEqual(r.spine_index, 0)

    def test_chapter_and_drawer(self):
        self.assertGreater(len(self.records), 0, 'No records parsed')
        for r in self.records:
            if r.chapter:
                self.assertIn(r.drawer, ('lighten', 'underscore', 'strikeout', 'invert'))

    def test_datetime_parseable(self):
        self.assertGreater(len(self.records), 0, 'No records parsed')
        for r in self.records:
            if r.datetime_str:
                ts = parse_timestamp(r.datetime_str)
                self.assertIsNotNone(ts, f'Cannot parse {r.datetime_str}')


if __name__ == '__main__':
    unittest.main()
