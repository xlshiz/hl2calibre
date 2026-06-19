import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mrexpt_parser import parse_mrexpt, decode_color, ms_to_iso, COLOR_NAME_MAP


# ── Minimal inline .mrexpt content ─────────────────────────────────────────

# 16 records, with seq starting at 26, covering various features:
# - Normal highlight (record 1: seq=26, first record with specific values)
# - Note/批注 (record 7: seq=32, has note content)
# - <BR> replacement (record 12: seq=37, raw text has <BR>)
# - Different colors (records use -28160=orange, -256=yellow, -65536=red)

MREXPT_CONTENT = """\
0
indent:false
trim:false
#
26
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
52
0
483
28
-28160
1671754358620


集合的外延表示法中，{}用来表示集合
1
0
0
#
27
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
51
0
203
12
-28160
1671754370000


数学能够为我们带来新的发现
1
0
0
#
28
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
36
0
392
14
-256
1671754400000


蕴含着丰富的知识
1
0
0
#
29
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
25
0
670
8
-28160
1671754420000


集合的元素
1
0
0
#
30
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
58
0
7020
10
-28160
1671754450000


有序对
1
0
0
#
31
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
33
0
480
14
-28160
1671754480000


这个定理很重要
1
0
0
#
32
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
41
0
410
10
-65536
1671754500000
1
这是一条批注笔记
核心概念需要理解
1
0
0
#
33
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
50
0
680
9
-28160
1671754530000


一致性证明
1
0
0
#
34
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
21
0
890
12
-28160
1671754560000


形式系统
1
0
0
#
35
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
16
0
427
9
-256
1671754590000


递归函数
1
0
0
#
36
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
42
0
200
16
-28160
1671754620000


哥德尔编码的巧妙之处
1
0
0
#
37
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
55
0
300
14
-28160
1671754650000


集合<BR>论是数学的<BR>基础
1
0
0
#
38
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
11
0
380
12
-28160
1671754680000


皮亚诺公理
1
0
0
#
39
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
23
0
519
10
-28160
1671754710000


数学归纳法
1
0
0
#
40
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
64
0
155
8
-28160
1671754740000


不可判定
1
0
0
#
41
数学女孩3：哥德尔不完备定理
/sdcard/Books/数学女孩3_哥德尔不完备定理.epub
/sdcard/books/数学女孩3_哥德尔不完备定理.epub
60
0
7600
7
-28160
1671754770000


形式证明
1
0
0
"""


def _parse_inline(content: str):
    """Helper: write inline mrexpt content to temp file and parse it."""
    with tempfile.NamedTemporaryFile(
        suffix='.mrexpt', mode='w', encoding='utf-8', delete=False
    ) as f:
        f.write(content)
        tmp_path = f.name
    try:
        return parse_mrexpt(tmp_path)
    finally:
        os.unlink(tmp_path)


class TestMrexptParser(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.records = _parse_inline(MREXPT_CONTENT)

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
        """Records with <BR> should have it replaced with newline."""
        rec = [r for r in self.records if '<BR>' in r.highlighted_text_raw]
        self.assertGreater(len(rec), 0, 'No record with <BR> found')
        rec = rec[0]
        self.assertIn('\n', rec.highlighted_text)
        self.assertNotIn('<BR>', rec.highlighted_text)
        # Verify the specific BR content
        self.assertEqual(rec.highlighted_text, '集合\n论是数学的\n基础')

    def test_timestamp_conversion(self):
        self.assertIn('2022-12-23', ms_to_iso(1671754358620))

    def test_note_content(self):
        """Records with notes/批注 should preserve the note text."""
        rec = [r for r in self.records if r.note]
        self.assertGreater(len(rec), 0, 'No record with note found')
        self.assertIn('这是一条批注笔记', rec[0].note)

    def test_different_colors(self):
        """Multiple color codes should be parsed correctly."""
        colors = {r.color_code for r in self.records}
        self.assertIn(-28160, colors)   # 橙色
        self.assertIn(-256, colors)     # 黄色
        self.assertIn(-65536, colors)   # 红色


if __name__ == '__main__':
    unittest.main()
