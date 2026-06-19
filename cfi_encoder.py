import bisect
from typing import Optional
from lxml import etree


def build_text_map(root) -> tuple[str, list[tuple]]:
    flat_text = []
    node_map = []
    _walk(root, flat_text, node_map)
    return ''.join(flat_text), node_map


def _walk(elem, flat_text, node_map, offset=0):
    if isinstance(elem, etree._Comment):
        return offset
    if elem.text:
        node_map.append((elem, 'text', offset, len(elem.text)))
        flat_text.append(elem.text)
        offset += len(elem.text)
    for child in elem:
        offset = _walk(child, flat_text, node_map, offset)
        if child.tail:
            node_map.append((child, 'tail', offset, len(child.tail)))
            flat_text.append(child.tail)
            offset += len(child.tail)
    return offset


def _normalize(text: str) -> str:
    """Normalize whitespace for fuzzy matching."""
    return ' '.join(text.split())


def find_text_in_html(root, search_text: str, flat_text=None, node_map=None,
                       norm_flat=None) -> Optional[tuple]:
    if flat_text is None or node_map is None:
        flat_text, node_map = build_text_map(root)
    text_len = len(search_text)

    # Try exact match first
    pos = flat_text.find(search_text)
    if pos != -1:
        return _result_at(node_map, pos, text_len)

    # Try normalized match (use cached norm_flat if available)
    if norm_flat is None:
        norm_flat = _normalize(flat_text)
    norm_search = _normalize(search_text)
    pos = norm_flat.find(norm_search)
    if pos != -1:
        orig_pos = _map_normalized_pos(flat_text, norm_flat, pos)
        if orig_pos is not None:
            return _result_at(node_map, orig_pos, text_len)

    # Try first N chars of search text (for long highlights split across nodes)
    if len(search_text) > 20:
        prefix = search_text[:20]
        pos = flat_text.find(prefix)
        if pos != -1:
            return _result_at(node_map, pos, text_len)
        norm_prefix = _normalize(prefix)
        pos = norm_flat.find(norm_prefix)
        if pos != -1:
            orig_pos = _map_normalized_pos(flat_text, norm_flat, pos)
            if orig_pos is not None:
                return _result_at(node_map, orig_pos, text_len)

    return None


def _result_at(node_map, pos, text_length=None):
    # Binary search: node_map is sorted by start position
    i = bisect.bisect_right(node_map, pos, key=lambda e: e[2]) - 1
    if i >= 0:
        elem, attr, start, length = node_map[i]
        if start <= pos < start + length:
            char_offset = pos - start
            cfi_path = _encode_cfi_path(elem, attr, char_offset)

            end_cfi_path = None
            if text_length is not None:
                end_offset = char_offset + text_length
                if end_offset <= length:
                    end_cfi_path = _encode_cfi_path(elem, attr, end_offset)
                else:
                    end_cfi_path = _encode_cfi_path(elem, attr, length)

            return (elem, attr, char_offset, cfi_path, end_cfi_path)
    return None


def _map_normalized_pos(original: str, normalized: str, norm_pos: int) -> Optional[int]:
    """Map a position in normalized text back to original text."""
    orig_idx = 0
    norm_idx = 0
    while norm_idx < norm_pos and orig_idx < len(original):
        if original[orig_idx].isspace():
            orig_idx += 1
            # Skip consecutive whitespace in original
            while orig_idx < len(original) and original[orig_idx].isspace():
                orig_idx += 1
            # One space in normalized
            norm_idx += 1
        else:
            orig_idx += 1
            norm_idx += 1
    return orig_idx if orig_idx < len(original) else None


def _cfi_step_index(parent, child):
    """Compute CFI step index for child within parent.

    Uses the same algorithm as Calibre's viewer, accounting for tail text
    nodes that exist in the browser DOM but not in lxml's tree.

    In the browser DOM, an element's tail text becomes a separate text node
    AFTER the element. So for each preceding sibling:
      - element: step +2 (even step)
      - element with tail text: step +2 for element, +1 for tail text node
    """
    index = 0
    for c in parent:
        is_elem = isinstance(c.tag, str)
        index |= 1
        if is_elem:
            index += 1
        if c is child:
            break
        # In browser DOM, tail text after an element becomes a text node sibling
        if is_elem and c.tail and c.tail.strip():
            index += 1
    return index


def _encode_cfi_path(target_elem, attr, char_offset) -> str:
    # Walk from target to root (stop before document node)
    chain = []
    current = target_elem
    while current is not None:
        chain.append(current)
        current = current.getparent()
    # Remove the document node (not a real element)
    if chain and not isinstance(chain[-1], etree._Element):
        chain.pop()
    chain.reverse()

    steps = []
    for elem in chain:
        parent = elem.getparent()
        elem_id = elem.get('id')
        if parent is not None:
            step = _cfi_step_index(parent, elem)
        else:
            # Root element (<html>): first element child of document → step 2
            step = 2
        id_suffix = f'[{elem_id}]' if elem_id else ''
        steps.append(f'{step}{id_suffix}')

    # For text/tail content, add step to the text node itself
    if attr == 'text':
        # elem.text is the first child (text node) of elem → step 1
        steps.append('1')
    elif attr == 'tail':
        # tail text is a text node AFTER elem in parent, step = elem_step + 1
        parent = target_elem.getparent()
        if parent is not None:
            elem_step = _cfi_step_index(parent, target_elem)
            steps.append(str(elem_step + 1))
        else:
            steps.append('3')  # root element tail: after step 2, next is 3

    path = '/' + '/'.join(steps)
    return f'{path}:{char_offset}'


def compute_full_cfi(spine_index, cfi_path) -> str:
    dom_position = spine_index * 2 + 1
    spine_step = (dom_position + 1) * 2
    return f'epubcfi(/6/{spine_step}!{cfi_path})'
