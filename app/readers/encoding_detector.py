from __future__ import annotations
import chardet


_BOM_MAP = {
    b"\xef\xbb\xbf": "utf-8-sig",
    b"\xff\xfe\x00\x00": "utf-32-le",
    b"\x00\x00\xfe\xff": "utf-32-be",
    b"\xff\xfe": "utf-16-le",
    b"\xfe\xff": "utf-16-be",
}


def detect_encoding(path: str) -> str:
    try:
        with open(path, "rb") as f:
            raw = f.read(8192)
    except OSError:
        return "utf-8"

    for bom, enc in _BOM_MAP.items():
        if raw.startswith(bom):
            return enc

    result = chardet.detect(raw)
    encoding = result.get("encoding") or "utf-8"
    confidence = result.get("confidence", 0.0)

    if confidence < 0.5:
        return "utf-8"
    return encoding
