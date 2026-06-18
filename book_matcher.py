import re
from typing import Optional


def find_book_by_title(db, title: str) -> Optional[int]:
    exact_query = f'title:"={title}"'
    ids = db.search(exact_query)
    if ids:
        return next(iter(ids))

    cleaned = _clean_title(title)
    if cleaned != title:
        fuzzy_query = f'title:"={cleaned}"'
        ids = db.search(fuzzy_query)
        if ids:
            return next(iter(ids))

    return None


def find_book(db, title: str, file_path: str) -> Optional[int]:
    return find_book_by_title(db, title)


def _clean_title(title: str) -> str:
    return re.split(r'\s*[：:—–-]\s*', title, maxsplit=1)[0].strip()


def _names_match(a: str, b: str) -> bool:
    a_lower = a.lower()
    b_lower = b.lower()
    if a_lower == b_lower:
        return True
    return a_lower in b_lower or b_lower in a_lower
