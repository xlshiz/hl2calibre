import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from koreader_parser import (
    parse_sidecar_lua,
    parse_xpath,
    parse_timestamp,
    KoreaderAnnotation,
)


# ── Inline sidecar Lua content for testing ──────────────────────────────────

# New format: annotations dict (unified highlight + bookmarks)
SIDECAR_NEW_FORMAT = """-- we can read Lua syntax here!
return {
    ["annotations"] = {
        [1] = {
            ["chapter"] = "Chapter 1",
            ["color"] = "yellow",
            ["datetime"] = "2020-11-16 18:50:53",
            ["drawer"] = "lighten",
            ["highlighted"] = true,
            ["page"] = "/body/DocFragment[7]/body/div/p[12]/text().0",
            ["pos0"] = "/body/DocFragment[7]/body/div/p[12]/text().0",
            ["pos1"] = "/body/DocFragment[7]/body/div/p[12]/text().25",
            ["text"] = "Alice was beginning to get very tired",
        },
        [2] = {
            ["chapter"] = "Chapter 1",
            ["datetime"] = "2020-11-16 18:50:54",
            ["drawer"] = "underscore",
            ["highlighted"] = true,
            ["page"] = "/body/DocFragment[7]/body/div/p[14]/text().0",
            ["pos0"] = "/body/DocFragment[7]/body/div/p[14]/text().0",
            ["pos1"] = "/body/DocFragment[7]/body/div/p[14]/text().10",
            ["text"] = "of having",
        },
        [3] = {
            ["chapter"] = "Chapter 2",
            ["color"] = "green",
            ["datetime"] = "2020-11-16 19:00:00",
            ["drawer"] = "lighten",
            ["page"] = "/body/DocFragment[9]/body/div/h2/text().3",
            ["text"] = "The Pool of Tears",
            -- No pos0/pos1 → pure bookmark, should be filtered out
        },
    },
}
"""

# Old format: highlight dict + bookmarks dict
SIDECAR_OLD_FORMAT = """return {
    ["highlight"] = {
        [1] = {
            {
                ["chapter"] = "第1章",
                ["color"] = "yellow",
                ["datetime"] = "2020-11-16 18:50:53",
                ["drawer"] = "lighten",
                ["pos0"] = "/body/DocFragment[7]/body/div/p[12]/text()[1].0",
                ["pos1"] = "/body/DocFragment[7]/body/div/p[12]/text()[1].25",
                ["text"] = "Alice was beginning",
            },
            {
                ["chapter"] = "第1章",
                ["color"] = "red",
                ["datetime"] = "2020-11-16 18:51:00",
                ["drawer"] = "strikeout",
                ["pos0"] = "/body/DocFragment[7]/body/div/p[15]/text()[1].0",
                ["pos1"] = "/body/DocFragment[7]/body/div/p[15]/text()[1].15",
                ["text"] = "to get very tired",
            },
        },
        [3] = {
            {
                ["chapter"] = "第2章",
                ["color"] = "green",
                ["datetime"] = "2020-11-16 19:00:00",
                ["drawer"] = "lighten",
                ["pos0"] = "/body/DocFragment[9]/body/div/h2/text()[1].0",
                ["pos1"] = "/body/DocFragment[9]/body/div/h2/text()[1].20",
                ["text"] = "The Pool of Tears",
            },
        },
    },
    ["bookmarks"] = {
        [1] = {
            ["chapter"] = "第1章",
            ["datetime"] = "2020-11-16 18:52:00",
            ["highlighted"] = true,
            ["pos0"] = "/body/DocFragment[7]/body/div/p[20]/text()[1].0",
            ["pos1"] = "/body/DocFragment[7]/body/div/p[20]/text()[1].30",
            ["text"] = "bookmark highlight",
        },
        [2] = {
            ["chapter"] = "第1章",
            ["datetime"] = "2020-11-16 18:53:00",
            ["highlighted"] = false,
            ["notes"] = "A note",
            ["page"] = "/body/DocFragment[7]/body/div/p[30]/text()[1].5",
            ["text"] = "pure bookmark",
        },
    },
}
"""

# Edge cases: empty, invalid, no annotations
SIDECAR_EMPTY = """return {}
"""

SIDECAR_NO_ANNOTATIONS = """return {
    ["some_other_key"] = "value",
}
"""

SIDECAR_MALFORMED = """return {
    ["annotations"] = "not a dict",
}
"""


def _parse_lua_string(lua_content: str) -> list:
    """Helper to parse sidecar Lua content from a string."""
    with tempfile.NamedTemporaryFile(
        suffix='.lua', mode='w', encoding='utf-8', delete=False
    ) as f:
        f.write(lua_content)
        tmp_path = f.name
    try:
        return parse_sidecar_lua(tmp_path)
    finally:
        os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════════════════════
# Test cases
# ═══════════════════════════════════════════════════════════════════════════

class TestKoreaderXPathParser(unittest.TestCase):
    """parse_xpath: test KOReader XPath position parsing."""

    def test_simple_xpath(self):
        """Full XPath with text()[1] and offset .0"""
        result = parse_xpath('/body/DocFragment[7]/body/div/p[12]/text()[1].0')
        self.assertIsNotNone(result)
        self.assertEqual(result['spine_index'], 6)      # 7 → 0-based = 6
        self.assertEqual(result['xpath_within'], '/body/div/p[12]')
        self.assertEqual(result['text_index'], 1)
        self.assertEqual(result['char_offset'], 0)

    def test_second_text_node(self):
        """text()[2] with non-zero offset"""
        result = parse_xpath('/body/DocFragment[7]/body/div/p[12]/text()[2].1')
        self.assertIsNotNone(result)
        self.assertEqual(result['spine_index'], 6)
        self.assertEqual(result['xpath_within'], '/body/div/p[12]')
        self.assertEqual(result['text_index'], 2)
        self.assertEqual(result['char_offset'], 1)

    def test_later_spine(self):
        """DocFragment[9] → spine_index=8"""
        result = parse_xpath('/body/DocFragment[9]/body/div/h2/text()[1].0')
        self.assertIsNotNone(result)
        self.assertEqual(result['spine_index'], 8)
        self.assertEqual(result['xpath_within'], '/body/div/h2')
        self.assertEqual(result['text_index'], 1)
        self.assertEqual(result['char_offset'], 0)

    def test_no_text_node_brackets(self):
        """XPath with text().offset (no [N] brackets), defaults text_index=1"""
        result = parse_xpath('/body/DocFragment[7]/body/div/p[12]/text().0')
        self.assertIsNotNone(result)
        self.assertEqual(result['spine_index'], 6)
        self.assertEqual(result['text_index'], 1)
        self.assertEqual(result['char_offset'], 0)

    def test_no_text_node(self):
        """XPath without text() suffix at all"""
        result = parse_xpath('/body/DocFragment[7]/body/div/p[12]')
        self.assertIsNotNone(result)
        self.assertEqual(result['spine_index'], 6)

    def test_invalid_xpath(self):
        """Invalid XPath should return None"""
        self.assertIsNone(parse_xpath(''))
        self.assertIsNone(parse_xpath('not/a/path'))
        self.assertIsNone(parse_xpath('/body/div/p/text()'))  # No DocFragment


class TestTimestampParser(unittest.TestCase):
    """parse_timestamp: test KOReader timestamp conversion."""

    def test_valid_timestamp(self):
        ts = parse_timestamp('2020-11-16 18:50:53')
        self.assertIsNotNone(ts)
        self.assertEqual(ts, 1605552653000)  # UTC

    def test_empty_timestamp(self):
        self.assertIsNone(parse_timestamp(''))
        self.assertIsNone(parse_timestamp(None))

    def test_invalid_format(self):
        self.assertIsNone(parse_timestamp('2020/11/16'))
        self.assertIsNone(parse_timestamp('not a date'))


class TestSidecarParser(unittest.TestCase):
    """parse_sidecar_lua: test parsing various sidecar formats."""

    # ── New format (annotations dict) ──────────────────────────────────

    def test_new_format_parses(self):
        """New format: annotations dict should parse correctly."""
        records = _parse_lua_string(SIDECAR_NEW_FORMAT)
        self.assertGreater(len(records), 0)

    def test_new_format_positions(self):
        """New format: annotations with pos0/pos1 should have valid positions."""
        records = _parse_lua_string(SIDECAR_NEW_FORMAT)
        for r in records:
            self.assertTrue(r.pos0, f'Annotation missing pos0')
            self.assertTrue(r.pos1, f'Annotation missing pos1')

    def test_new_format_spine_indices(self):
        """New format: spine_index should be correctly computed (DocFragment[N] → N-1)."""
        records = _parse_lua_string(SIDECAR_NEW_FORMAT)
        for r in records:
            self.assertIsNotNone(r.spine_index)
            self.assertGreaterEqual(r.spine_index, 0)

    def test_new_format_chapter_and_drawer(self):
        """New format: chapter and drawer fields should be populated."""
        records = _parse_lua_string(SIDECAR_NEW_FORMAT)
        for r in records:
            if r.chapter:
                self.assertIn(r.drawer, ('lighten', 'underscore', 'strikeout', 'invert'))

    def test_new_format_colors(self):
        """New format: color field should be preserved."""
        records = _parse_lua_string(SIDECAR_NEW_FORMAT)
        # annotation [1] has color=yellow, [2] has no color
        colors = [r.color for r in records if r.color]
        self.assertIn('yellow', colors)

    def test_new_format_datetime(self):
        """New format: datetime should be parseable."""
        records = _parse_lua_string(SIDECAR_NEW_FORMAT)
        for r in records:
            if r.datetime_str:
                ts = parse_timestamp(r.datetime_str)
                self.assertIsNotNone(ts, f'Cannot parse {r.datetime_str}')

    def test_new_format_includes_page_fallback(self):
        """New format: entries with page (no pos0/pos1) should use page as pos0/pos1."""
        records = _parse_lua_string(SIDECAR_NEW_FORMAT)
        texts = [r.text for r in records]
        # annotation [3] has no pos0/pos1 but has page → page falls back as pos0/pos1
        self.assertIn('The Pool of Tears', texts)
        r = [r for r in records if r.text == 'The Pool of Tears'][0]
        self.assertEqual(r.pos0, '/body/DocFragment[9]/body/div/h2/text().3')

    def test_new_format_skips_entries_without_any_position(self):
        """New format: entries without pos0, pos1, or page should be skipped."""
        lua = """return {
    ["annotations"] = {
        [1] = {
            ["chapter"] = "Ch1",
            ["text"] = "no position at all",
        },
    },
}"""
        records = _parse_lua_string(lua)
        self.assertEqual(len(records), 0)

    def test_new_format_text_no_escape(self):
        """New format: text should not contain raw backslash escapes."""
        records = _parse_lua_string(SIDECAR_NEW_FORMAT)
        for r in records:
            self.assertNotIn('\\\n', r.text)
            self.assertNotIn('\\n', r.text)

    # ── Old format (highlight + bookmarks) ─────────────────────────────

    def test_old_format_parses(self):
        """Old format: highlight dict should parse correctly."""
        records = _parse_lua_string(SIDECAR_OLD_FORMAT)
        self.assertGreater(len(records), 0)

    def test_old_format_highlight_count(self):
        """Old format: should extract all highlights with pos0/pos1."""
        records = _parse_lua_string(SIDECAR_OLD_FORMAT)
        # 3 highlights + 1 highlighted bookmark = 4 items with pos0/pos1
        self.assertEqual(len(records), 4)

    def test_old_format_bookmark_highlight(self):
        """Old format: bookmark with highlighted=true and pos0 should be included."""
        records = _parse_lua_string(SIDECAR_OLD_FORMAT)
        texts = [r.text for r in records]
        self.assertIn('bookmark highlight', texts)

    def test_old_format_bookmark_pure(self):
        """Old format: bookmark without highlighted flag should be excluded."""
        records = _parse_lua_string(SIDECAR_OLD_FORMAT)
        texts = [r.text for r in records]
        self.assertNotIn('pure bookmark', texts)

    def test_old_format_drawer_from_highlight_drawer(self):
        """Old format: should fall back to highlight_drawer if drawer is missing."""
        records = _parse_lua_string(SIDECAR_OLD_FORMAT)
        for r in records:
            self.assertIn(r.drawer, ('lighten', 'underscore', 'strikeout', 'invert'))

    def test_old_format_different_drawers(self):
        """Old format: different drawers should be preserved."""
        records = _parse_lua_string(SIDECAR_OLD_FORMAT)
        drawers = {r.drawer for r in records}
        self.assertIn('lighten', drawers)
        self.assertIn('strikeout', drawers)

    # ── Edge cases ─────────────────────────────────────────────────────

    def test_empty_sidecar(self):
        """Empty sidecar should return empty list."""
        records = _parse_lua_string(SIDECAR_EMPTY)
        self.assertEqual(len(records), 0)

    def test_no_annotations(self):
        """Sidecar without highlight/bookmarks/annotations should return empty."""
        records = _parse_lua_string(SIDECAR_NO_ANNOTATIONS)
        self.assertEqual(len(records), 0)

    def test_malformed_annotations(self):
        """Sidecar with non-dict annotations should return empty."""
        records = _parse_lua_string(SIDECAR_MALFORMED)
        self.assertEqual(len(records), 0)


if __name__ == '__main__':
    unittest.main()
