"""KOReader 侧边文件（sidecar Lua）解析器。

KOReader 为每本 EPUB 书籍维护一个侧边文件：
  <书名>.sdr/metadata.epub.lua

该文件以 Lua table 格式存储阅读进度、书签和高亮标注。

标注存储在两个地方：
  - highlight: 高亮（按页码分组）
  - bookmarks: 书签（含可能是高亮的条目）

参考：
  - https://github.com/renke/koreader-to-calibre-highlights
  - https://github.com/kyxap/koreader-calibre-plugin
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

try:
    from .slpp import slpp as lua
except ImportError:
    from slpp import slpp as lua


@dataclass
class KoreaderAnnotation:
    """单条 KOReader 标注。"""

    # KOReader 原始字段
    text: str                          # 高亮原文
    pos0: str                          # 起始 XPath, e.g. /body/DocFragment[7]/body/div/p[12]/text()[1].0
    pos1: str                          # 结束 XPath
    chapter: str                       # 章节标题
    datetime_str: str                  # 时间戳字符串, e.g. "2020-11-16 18:50:53"
    drawer: str = 'lighten'            # 绘制方式: lighten, underscore, strikeout, invert
    color: Optional[str] = None        # 颜色: red, orange, yellow, green, olive, cyan, blue, purple, gray
    notes: str = ''                    # 读者批注
    sort_key: int = 0                  # 排序键（用于保留顺序）

    # 解析后的位置信息
    spine_index: Optional[int] = None  # 从 pos0 解析
    xpath_within: Optional[str] = None # 从 pos0 解析（DocFragment 内路径）
    text_index: Optional[int] = None   # 从 pos0 解析（text()[N] 中的 N）
    char_offset: int = 0               # 从 pos0 解析


# KOReader XPath 模式:
# /body/DocFragment[N]/rest/of/xpath/text()[M].offset
_XPATH_RE = re.compile(
    r'/body/DocFragment\[(\d+)\](.*?)(?:/text\(\)(?:\[(\d+)\])?\.(\d+))?$'
)


def parse_xpath(xpath: str) -> Optional[dict]:
    """解析 KOReader 的 XPath 位置字符串。

    Args:
        xpath: KOReader 位置, e.g.
            "/body/DocFragment[7]/body/div/p[12]/text()[1].0"

    Returns:
        {spine_index, xpath_within, text_index, char_offset} 或 None
    """
    m = _XPATH_RE.search(xpath)
    if not m:
        return None
    doc_fragment = int(m.group(1))
    xpath_within = m.group(2)  # e.g. /body/div/p[12]
    text_index_str = m.group(3)
    offset_str = m.group(4)

    return {
        'spine_index': doc_fragment - 1,     # KOReader 1-based → 0-based
        'xpath_within': xpath_within or '',
        'text_index': int(text_index_str) if text_index_str else 1,
        'char_offset': int(offset_str) if offset_str else 0,
    }


def parse_sidecar_lua(filepath: str) -> list[KoreaderAnnotation]:
    """解析 KOReader 侧边 Lua 文件，提取所有标注。

    Args:
        filepath: 侧边文件路径, e.g. "metadata.epub.lua"

    Returns:
        KoreaderAnnotation 列表（按位置排序）
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 去掉 Lua 文件头注释和 return 前缀，只保留 table 部分
    # 格式: "-- we can read Lua syntax here!\nreturn { ... }"
    clean = re.sub(r'^[^{]*', '', content).strip()
    if not clean:
        return []

    data = lua.decode(clean)
    if not isinstance(data, dict):
        return []

    annotations = []
    sort_counter = 0

    # 1. 从 annotations 字典提取（KOReader 新版格式，统一存储高亮和书签）
    raw_annots = data.get('annotations', {})
    if isinstance(raw_annots, dict):
        for k, v in raw_annots.items():
            if isinstance(v, dict):
                items = [v]
            elif isinstance(v, list):
                items = v
            else:
                continue
            for a in items:
                if isinstance(a, dict):
                    pos = a.get('pos0', '') or a.get('page', '')
                    if pos:
                        annotations.append(_dict_to_annotation(a, sort_counter))
                        sort_counter += 1

    # 2. 从 highlight 字典提取（KOReader 旧版纯高亮存储，按页码分组）
    highlights = data.get('highlight', {})
    if isinstance(highlights, dict):
        for page_key, page_highlights in highlights.items():
            entries = []
            if isinstance(page_highlights, list):
                entries = page_highlights
            elif isinstance(page_highlights, dict):
                # 单条高亮可能被解码为 dict 而非 list
                entries = [page_highlights]
            for h in entries:
                if isinstance(h, dict) and h.get('pos0') and h.get('pos1'):
                    annotations.append(_dict_to_annotation(h, sort_counter))
                    sort_counter += 1

    # 3. 从 bookmarks 字典/列表提取（旧版书签，某些高亮标记在其中）
    bookmarks = data.get('bookmarks', {})
    if isinstance(bookmarks, dict):
        items = list(bookmarks.values())
    elif isinstance(bookmarks, list):
        items = bookmarks
    else:
        items = []
    for bk in items:
        if isinstance(bk, dict):
            if bk.get('highlighted') and bk.get('pos0') and bk.get('pos1'):
                annotations.append(_dict_to_annotation(bk, sort_counter))
                sort_counter += 1

    # 按在书中的位置排序
    annotations.sort(key=lambda a: _sort_key(a))
    return annotations


def _dict_to_annotation(d: dict, sort_key: int) -> KoreaderAnnotation:
    """将 KOReader Lua 字典转为 KoreaderAnnotation。"""
    pos0 = str(d.get('pos0', '') or d.get('page', ''))
    pos1 = str(d.get('pos1', '') or d.get('page', ''))
    parsed = parse_xpath(pos0)
    notes = d.get('notes', d.get('note', ''))

    # KOReader 有时会在 text 中加入反斜杠转义换行
    text = str(d.get('text', ''))
    text = text.replace('\\\n', '\n').replace('\\n', '\n')

    return KoreaderAnnotation(
        text=text,
        pos0=pos0,
        pos1=pos1,
        chapter=str(d.get('chapter', '')),
        datetime_str=str(d.get('datetime', '')),
        drawer=str(d.get('drawer', d.get('highlight_drawer', 'lighten'))),
        color=d.get('color', None),
        notes=str(notes) if notes else '',
        sort_key=sort_key,
        spine_index=parsed['spine_index'] if parsed else None,
        xpath_within=parsed['xpath_within'] if parsed else None,
        text_index=parsed['text_index'] if parsed else None,
        char_offset=parsed['char_offset'] if parsed else 0,
    )


def _sort_key(a: KoreaderAnnotation) -> tuple:
    """按 spine 索引 + 章节 + 偏移排序。"""
    si = a.spine_index if a.spine_index is not None else 99999
    return (si, a.chapter or '', a.char_offset, a.sort_key)


def parse_timestamp(datetime_str: str) -> Optional[int]:
    """将 KOReader 时间戳字符串转为毫秒时间戳。

    KOReader 格式: "2020-11-16 18:50:53"
    按 UTC 解析（KOReader 使用 UTC 时间）。
    """
    if not datetime_str:
        return None
    try:
        dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
        dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None
