from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class MrexptRecord:
    seq: int
    title: str
    file_path: str
    file_path_lower: str
    chapter: int
    unknown1: int
    offset: int
    length: int
    color_code: int
    timestamp_ms: int
    unknown_flag: str
    note: str
    _highlighted_text: str
    flag1: int
    flag2: int
    flag3: int

    @property
    def highlighted_text(self) -> str:
        text = self._highlighted_text
        text = text.replace('<BR>', '\n')
        text = text.replace('\uFFFC', '')
        return text

    @property
    def highlighted_text_raw(self) -> str:
        return self._highlighted_text

    @property
    def color_hex(self) -> str:
        return decode_color(self.color_code)

    @property
    def color_name(self) -> str:
        return COLOR_NAME_MAP.get(self.color_hex.upper(), self.color_hex)

    @property
    def timestamp_iso(self) -> str:
        return ms_to_iso(self.timestamp_ms)


def decode_color(code: int) -> str:
    return hex((0xFFFFFFFF + code + 1) & 0xFFFFFFFF)[2:].zfill(8)[2:].upper()


def ms_to_iso(ms: int) -> str:
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return dt.isoformat()


# Map Moon+ Reader color hex values to Calibre built-in color names.
# Calibre only supports: yellow, green, blue, red, purple.
COLOR_NAME_MAP = {
    'FF0000': 'red',      # pure red
    'FFFF00': 'yellow',   # pure yellow
    'FF9200': 'yellow',   # orange -> closest Calibre builtin
    '00FF00': 'green',
    '00FFFF': 'blue',     # cyan -> closest Calibre builtin
    '0000FF': 'blue',
    'FF00FF': 'purple',
    '800080': 'purple',   # dark purple
    'FFC000': 'yellow',   # amber -> yellow
    '00BFFF': 'blue',     # deep sky blue -> blue
    '32CD32': 'green',    # lime green -> green
}


def parse_mrexpt(filepath: str) -> list[MrexptRecord]:
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\n') for line in f]

    records = []
    i = 3
    while i < len(lines):
        if lines[i] == '#':
            i += 1
            if i + 16 <= len(lines):
                record = _parse_record(lines[i:i + 16])
                records.append(record)
                i += 16
            else:
                break
        else:
            i += 1
    return records


def _parse_record(lines: list[str]) -> MrexptRecord:
    return MrexptRecord(
        seq=int(lines[0]),
        title=lines[1],
        file_path=lines[2],
        file_path_lower=lines[3],
        chapter=int(lines[4]),
        unknown1=int(lines[5]),
        offset=int(lines[6]),
        length=int(lines[7]),
        color_code=int(lines[8]),
        timestamp_ms=int(lines[9]),
        unknown_flag=lines[10],
        note=lines[11],
        _highlighted_text=lines[12],
        flag1=int(lines[13]),
        flag2=int(lines[14]),
        flag3=int(lines[15]),
    )
