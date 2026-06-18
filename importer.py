import hashlib
import os
import zipfile
from lxml import etree
from .mrexpt_parser import parse_mrexpt
from .cfi_encoder import find_text_in_html, build_text_map
from .converter import convert_record


def _clear_viewer_cache(epub_path):
    """Delete the viewer annotation cache file for this EPUB.

    The viewer caches annotations locally and merges them with DB annotations
    on open. Stale 'removed' entries in the cache can overwrite our fresh
    imports during merge (newer timestamp wins).
    """
    try:
        from calibre.utils.config import json_config
        annots_dir = os.path.join(json_config('viewer').dir, 'annots')
    except Exception:
        return
    if not os.path.isdir(annots_dir):
        return
    path_key = hashlib.sha256(os.path.abspath(epub_path).encode()).hexdigest()
    cache_file = os.path.join(annots_dir, f'{path_key}.json')
    if os.path.exists(cache_file):
        os.remove(cache_file)


def import_mrexpt(db, book_id, mrexpt_path) -> dict:
    """Import .mrexpt annotations into a specific book in Calibre.

    Args:
        db: Calibre database cache (new_api)
        book_id: target book ID (user-selected)
        mrexpt_path: path to .mrexpt file

    Returns:
        {success, skipped, failed, errors, details}
    """
    records = parse_mrexpt(mrexpt_path)
    if not records:
        return {'success': 0, 'skipped': 0, 'failed': 0, 'errors': ['文件为空或格式错误'], 'details': []}

    # Verify title matches
    mi = db.get_metadata(book_id)
    calibre_title = (mi.title or '').strip()
    mrexpt_title = records[0].title.strip()
    if calibre_title and mrexpt_title and calibre_title != mrexpt_title:
        return {
            'success': 0, 'skipped': 0, 'failed': 0,
            'errors': [f'书名不匹配: 选中的是《{calibre_title}》，标注文件是《{mrexpt_title}》'],
            'details': [],
        }

    epub_path = db.format_abspath(book_id, 'EPUB')
    if not epub_path or not os.path.exists(epub_path):
        return {'success': 0, 'skipped': 0, 'failed': 0, 'errors': ['EPUB 文件不存在'], 'details': []}

    _clear_viewer_cache(epub_path)

    try:
        epub = _EpubSearch(epub_path)
        n = len(epub._spine_ids)
    except Exception as e:
        return {'success': 0, 'skipped': 0, 'failed': 0, 'errors': [f'打开 EPUB 失败: {e}'], 'details': []}

    annotations = []
    warnings = []
    best_spine = None

    for record in records:
        try:
            annot = _convert_record(record, book_id, epub, best_spine)
            annotations.append(annot)
            sc = annot.get('start_cfi')
            sn = annot.get('spine_name')
            si = annot.get('spine_index')
            txt = annot.get('highlighted_text', '')[:20]
            print(f'[hl2calibre] seq={record.seq}: spine={si} name={sn!r} cfi={sc!r} text={txt!r}')
            if 'start_cfi' not in annot:
                warnings.append(f'序号 {record.seq}: 无法精确定位')
            else:
                best_spine = annot['spine_index']
        except Exception as e:
            warnings.append(f'序号 {record.seq}: {e}')
            print(f'[hl2calibre] seq={record.seq}: ERROR {e}')

    print(f'[hl2calibre] {len(records)} records processed, {len(annotations)} OK')

    if not annotations:
        return {'success': 0, 'skipped': 0, 'failed': 0, 'errors': ['无有效标注'], 'details': []}

    try:
        db.merge_annotations_for_book(
            book_id, 'EPUB', annotations,
            user_type='local', user='viewer',
        )
        print(f'[hl2calibre] merge OK: {len(annotations)} annotations written')
    except Exception as e:
        print(f'[hl2calibre] merge FAILED: {e}')
        return {'success': 0, 'skipped': 0, 'failed': len(annotations), 'errors': [f'写入失败: {e}'], 'details': []}

    return {
        'success': len(annotations),
        'skipped': 0,
        'failed': 0,
        'errors': [],
        'details': [{'title': mrexpt_title, 'book_id': book_id, 'count': len(annotations), 'warnings': warnings}],
    }


def _convert_record(record, book_id, epub, best_spine=None):
    """Convert a single mrexpt record to Calibre annotation."""
    search_text = record.highlighted_text

    cfi_path = None
    end_cfi_path = None
    spine_name = None
    spine_index = record.chapter

    # Try best_spine first
    if best_spine is not None:
        cfi_path, end_cfi_path, spine_name = epub.search(best_spine, search_text)
        if cfi_path:
            spine_index = best_spine

    # Try specified chapter
    if cfi_path is None:
        cfi_path, end_cfi_path, spine_name = epub.search(record.chapter, search_text)
        if cfi_path:
            spine_index = record.chapter

    # Search other chapters
    if cfi_path is None:
        for idx in epub.spine_indices():
            if idx == record.chapter or idx == best_spine:
                continue
            cfi_path, end_cfi_path, spine_name = epub.search(idx, search_text)
            if cfi_path:
                spine_index = idx
                break

    return convert_record(record, spine_index=spine_index, cfi_path=cfi_path,
                          end_cfi_path=end_cfi_path, spine_name=spine_name, book_id=book_id)


class _EpubSearch:
    """Lazy-loading EPUB text searcher."""

    def __init__(self, epub_path):
        self._zf = zipfile.ZipFile(epub_path, 'r')
        self._cache = {}
        self._spine_ids, self._id_to_href, self._opf_dir, self._spine_names = self._parse()

    def _parse(self):
        opf_path = _find_opf(self._zf)
        if not opf_path:
            return [], {}, '', []
        opf_dir = os.path.dirname(opf_path)
        spine_ids, id_to_href = _parse_opf(self._zf, opf_path)
        spine_names = [id_to_href.get(sid, '') for sid in spine_ids]
        return spine_ids, id_to_href, opf_dir, spine_names

    def _canonical_name(self, item_id):
        """Get the canonical name (EPUB-root-relative path) for a spine item."""
        return self._id_to_href.get(item_id, '')

    def spine_indices(self):
        return range(len(self._spine_ids))

    def _load(self, idx):
        if idx in self._cache:
            return self._cache[idx]
        if idx >= len(self._spine_ids):
            return None
        item_id = self._spine_ids[idx]
        canonical_name = self._id_to_href.get(item_id)
        if not canonical_name:
            self._cache[idx] = None
            return None
        full_path = canonical_name
        try:
            raw = self._zf.read(full_path)
            tree = etree.HTML(raw)
            flat_text, node_map = build_text_map(tree)
            self._cache[idx] = (flat_text, node_map, tree)
            return self._cache[idx]
        except Exception:
            self._cache[idx] = None
            return None

    def search(self, idx, search_text):
        data = self._load(idx)
        if data is None:
            return None, None, None
        flat_text, node_map, tree = data
        result = find_text_in_html(tree, search_text, flat_text, node_map)
        if result:
            _, _, _, cfi_path, end_cfi_path = result
            spine_name = self._spine_names[idx] if idx < len(self._spine_names) else None
            return cfi_path, end_cfi_path, spine_name
        return None, None, None

    def close(self):
        self._zf.close()


def _find_opf(zf: zipfile.ZipFile):
    """Find the OPF file path from META-INF/container.xml."""
    try:
        container = zf.read('META-INF/container.xml')
        tree = etree.fromstring(container)
        ns = {'c': 'urn:oasis:names:tc:opendocument:xmlns:container'}
        rootfile = tree.find('.//c:rootfile', ns)
        if rootfile is not None:
            return rootfile.get('full-path')
    except Exception:
        pass
    for name in zf.namelist():
        if name.endswith('.opf'):
            return name
    return None


def _parse_opf(zf: zipfile.ZipFile, opf_path: str):
    """Parse OPF to get spine order and manifest.

    Returns:
        spine_ids: list of manifest idrefs in spine order
        id_to_href: mapping from manifest item id to canonical name
            (path relative to EPUB root, e.g. 'OEBPS/Text/part0000.xhtml')
    """
    content = zf.read(opf_path)
    tree = etree.fromstring(content)
    ns = {'opf': 'http://www.idpf.org/2007/opf'}
    opf_dir = os.path.dirname(opf_path)

    id_to_href = {}
    for item in tree.findall('.//opf:manifest/opf:item', ns):
        item_id = item.get('id')
        href = item.get('href')
        if item_id and href:
            # Resolve OPF-relative href to canonical name (relative to EPUB root)
            # This must match what Calibre's container.href_to_name() produces,
            # because the viewer compares spine_name with ===.
            if opf_dir:
                canonical = os.path.normpath(f'{opf_dir}/{href}').replace('\\', '/')
            else:
                canonical = href
            id_to_href[item_id] = canonical

    spine_ids = []
    for itemref in tree.findall('.//opf:spine/opf:itemref', ns):
        idref = itemref.get('idref')
        if idref:
            spine_ids.append(idref)

    return spine_ids, id_to_href
