import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mrexpt_parser import parse_mrexpt, decode_color, ms_to_iso, COLOR_NAME_MAP

EXAMPLE_FILE = os.path.join(os.path.dirname(__file__), '..', 'docs', 'example.mrexpt')


class TestMrexptParser(unittest.TestCase):
    def setUp(self):
        self.records = parse_mrexpt(EXAMPLE_FILE)

    def test_parse_header(self):
        self.assertGreater(len(self.records), 0)

    def test_parse_first_record(self):
        rec = self.records[0]
        self.assertEqual(rec.seq, 26)
        self.assertEqual(rec.title, '数学女孩3：哥德尔不完备定理')
        self.assertEqual(rec.chapter, 52)
        self.assertEqual(rec.offset, 483)
        self.assertEqual(rec.color_code, -28160)
        self.assertEqual(rec.timestamp_ms, 1671754358620)
        self.assertTrue(rec.highlighted_text.startswith('集合的外延'))
        self.assertEqual(rec.note, '')

    def test_parse_record_count(self):
        self.assertEqual(len(self.records), 16)

    def test_color_decode(self):
        self.assertEqual(decode_color(-28160), 'FF9200')
        self.assertEqual(decode_color(-65536), 'FF0000')
        self.assertEqual(decode_color(-256), 'FFFF00')

    def test_br_replacement(self):
        record_with_br = None
        for rec in self.records:
            if '<BR>' in rec.highlighted_text_raw:
                record_with_br = rec
                break
        self.assertIsNotNone(record_with_br, "No record with <BR> found")
        self.assertIn('\n', record_with_br.highlighted_text)
        self.assertNotIn('<BR>', record_with_br.highlighted_text)

    def test_timestamp_conversion(self):
        self.assertIn('2022-12-23', ms_to_iso(1671754358620))


if __name__ == '__main__':
    unittest.main()
