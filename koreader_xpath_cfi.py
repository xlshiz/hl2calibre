"""KOReader XPath → Calibre CFI 转换器。

KOReader 使用 XPath 格式定位文本：
    /body/DocFragment[N]/body/div/p[12]/text()[M].offset

Calibre 使用 CFI (Canonical Fragment Identifier) 格式：
    /2/4/2652/1:0

本模块将 XPath 转换为 CFI，用于写入 Calibre 标注系统。
"""

import os
import zipfile
from typing import Optional
from lxml import etree

try:
    from .cfi_encoder import _encode_cfi_path, _cfi_step_index
    from .koreader_parser import parse_xpath, KoreaderAnnotation
except ImportError:
    from cfi_encoder import _encode_cfi_path, _cfi_step_index
    from koreader_parser import parse_xpath, KoreaderAnnotation


# XHTML 命名空间
XHTML_NS = 'http://www.w3.org/1999/xhtml'


def _build_ns_xpath(xpath_within: str) -> str:
    """给 XPath 的元素步骤添加 XHTML 命名空间前缀。

    Args:
        xpath_within: 不带命名空间的 XPath, e.g. /body/div/p[12]

    Returns:
        带命名空间的 XPath, e.g. /ns:body/ns:div/ns:p[12]
    """
    parts = xpath_within.strip('/').split('/')
    ns_parts = []
    for part in parts:
        # 提取元素名和可能的下标
        m = __import__('re').match(r'^([a-zA-Z_][a-zA-Z0-9_]*)((?:\[[^\]]*\])*)$', part)
        if m:
            elem_name = m.group(1)
            predicates = m.group(2)
            ns_parts.append(f'ns:{elem_name}{predicates}')
        else:
            ns_parts.append(part)
    return '/ns:html' + ('/' + '/'.join(ns_parts) if ns_parts else '')


def _find_text_node(element: etree.Element, text_index: int) -> tuple:
    """在元素中查找第 N 个文本节点。

    模拟浏览器 DOM 的 text()[N] 语义：
      text()[1] → element.text
      text()[2] → first child 的 tail
      text()[3] → second child 的 tail
      ...

    Args:
        element: lxml 元素
        text_index: 文本节点索引（1-based）

    Returns:
        (target_elem, attr, accumulated_offset)
        - target_elem: 包含该文本段的元素
        - attr: 'text' 或 'tail'
        - accumulated_offset: 该文本段在完整文本流前的累积偏移
    """
    if text_index == 1:
        return element, 'text', 0

    # text_index > 1: 需要遍历子元素，查找 tail 文本
    idx = 1
    acc = len(element.text or '')
    for child in element:
        idx += 1
        if idx == text_index:
            return child, 'tail', acc
        acc += len(child.tail or '')
        # 递归：如果文本节点在子元素内部
        if idx < text_index:
            sub_result = _find_text_node_in_child(child, text_index - idx)
            if sub_result:
                sub_elem, sub_attr, sub_acc = sub_result
                return sub_elem, sub_attr, acc + sub_acc
            # 子元素可能有 tail
            idx += 1
            acc += len(child.tail or '')

    # 如果 text_index 超出范围，回退到 element.text
    return element, 'text', 0


def _find_text_node_in_child(element: etree.Element, target_idx: int) -> Optional[tuple]:
    """递归在子元素内部查找文本节点（支持嵌套元素）。"""
    idx = 1
    if element.text:
        if idx == target_idx:
            return element, 'text', 0
        idx += 1
    acc = len(element.text or '')
    for child in element:
        if idx == target_idx:
            return child, 'tail', acc
        acc += len(child.tail or '')
        idx += 1
        if idx < target_idx:
            sub = _find_text_node_in_child(child, target_idx - idx)
            if sub:
                return sub[0], sub[1], acc + sub[2]
        if child.tail:
            if idx == target_idx:
                return child, 'tail', acc
            idx += 1
            acc += len(child.tail or '')
    return None


def resolve_position(
    spine_html: etree.Element,
    xpath_within: str,
    text_index: int,
    char_offset: int,
) -> Optional[dict]:
    """在 spine HTML 中解析 KOReader 位置，返回 CFI 信息。

    Args:
        spine_html: 从 EPUB spine 中解析的 HTML 文档树
        xpath_within: 不带 DocFragment 前缀的 XPath, e.g. /body/div/p[12]
        text_index: text()[N] 中的 N (1-based)
        char_offset: 文本节点内的字符偏移

    Returns:
        {cfi_path, elem, attr, offset, char_offset} 或 None
    """
    ns_xpath = _build_ns_xpath(xpath_within)
    try:
        elements = spine_html.xpath(ns_xpath, namespaces={'ns': XHTML_NS})
    except etree.XPathEvalError:
        return None
    if not elements:
        # 尝试不带命名空间的 XPath（某些 EPUB 的非 XHTML 内容）
        fallback_xpath = '/html' + xpath_within
        try:
            elements = spine_html.xpath(fallback_xpath)
        except etree.XPathEvalError:
            return None
        if not elements:
            return None

    target_elem = elements[0]

    # 查找文本节点
    elem, attr, offset = _find_text_node(target_elem, text_index)

    # 使用 cfi_encoder 的 _encode_cfi_path 计算 CFI
    cfi_path = _encode_cfi_path(elem, attr, char_offset)

    return {
        'cfi_path': cfi_path,
        'elem': elem,
        'attr': attr,
        'offset': offset,
        'char_offset': char_offset,
    }


def resolve_annotation_position(
    spine_html: etree.Element,
    annotation: KoreaderAnnotation,
) -> tuple:
    """解析单条 KOReader 标注的起止 CFI。

    Args:
        spine_html: spine HTML 文档树
        annotation: KOReader 标注记录

    Returns:
        (start_cfi, end_cfi) 或 (None, None) 如果解析失败
    """
    # 解析 pos0 (起始位置)
    parsed0 = parse_xpath(annotation.pos0)
    if not parsed0:
        return None, None

    result0 = resolve_position(
        spine_html,
        parsed0['xpath_within'],
        parsed0['text_index'],
        parsed0['char_offset'],
    )
    if not result0:
        return None, None
    start_cfi = result0['cfi_path']

    # 解析 pos1 (结束位置)
    parsed1 = parse_xpath(annotation.pos1)
    if not parsed1:
        return start_cfi, None

    result1 = resolve_position(
        spine_html,
        parsed1['xpath_within'],
        parsed1['text_index'],
        parsed1['char_offset'],
    )
    if not result1:
        return start_cfi, start_cfi
    end_cfi = result1['cfi_path']

    return start_cfi, end_cfi


class XPathResolver:
    """EPUB spine HTML 的 XPath 解析器，带缓存。"""

    def __init__(self, epub_path: str):
        self._zf = zipfile.ZipFile(epub_path, 'r')
        self._html_cache = {}

    def get_spine_html(self, spine_index: int, spine_name: str) -> Optional[etree.Element]:
        """获取指定 spine 的 HTML 文档树。"""
        cache_key = (spine_index, spine_name)
        if cache_key in self._html_cache:
            return self._html_cache[cache_key]

        try:
            raw = self._zf.read(spine_name)
            tree = etree.HTML(raw)
            self._html_cache[cache_key] = tree
            return tree
        except Exception:
            return None

    def close(self):
        self._zf.close()
