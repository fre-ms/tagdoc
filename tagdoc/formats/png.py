"""A PNG: its XMP in an ``iTXt`` chunk ``XML:com.adobe.xmp``, its EXIF in an ``eXIf``
chunk (medRDS 7.4).  The picture's data are not touched.

The XMP is written exactly as the standard's reference library writes it
(``embedXmpPng``): the same bytes for the same picture and packet.
"""

from __future__ import annotations

import zlib

from tagdoc.formats.common import NoPlace

SIGNATURE = b"\x89PNG\r\n\x1a\n"
XMP = b"XML:com.adobe.xmp\0"


def is_png(data: bytes) -> bool:
    return data[:8] == SIGNATURE


def _chunks(data: bytes) -> list[tuple[bytes, int, int]]:
    """The chunks of the picture, as (type, start, end)."""
    if not is_png(data):
        raise NoPlace("not-png")
    found = []
    at = 8
    while at + 12 <= len(data):
        length = int.from_bytes(data[at:at + 4], "big")
        found.append((data[at + 4:at + 8], at, at + 12 + length))
        at += 12 + length
    if not found or found[0][0] != b"IHDR":
        raise NoPlace("not-png")
    return found


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (len(payload).to_bytes(4, "big") + kind + payload
            + zlib.crc32(kind + payload).to_bytes(4, "big"))


def exif_of(data: bytes) -> bytes | None:
    """The EXIF block of the picture, or None."""
    for kind, start, end in _chunks(data):
        if kind == b"eXIf":
            return data[start + 8:end - 4]
    return None


def with_exif(data: bytes, block: bytes) -> bytes:
    """The picture with ``block`` as its EXIF: in the place of the chunk it had, else
    right after its header."""
    made = _chunk(b"eXIf", block)
    chunks = _chunks(data)
    for kind, start, end in chunks:
        if kind == b"eXIf":
            return data[:start] + made + data[end:]
    head = chunks[0][2]
    return data[:head] + made + data[head:]


def with_packet(data: bytes, packet: str) -> bytes:
    """The picture with ``packet`` as its XMP, in place of any XMP it had; the reference
    library's ``embedXmpPng``, byte for byte."""
    kept = []
    for kind, start, end in _chunks(data):
        if not (kind == b"iTXt" and data[start + 8:start + 8 + len(XMP)] == XMP):
            kept.append(data[start:end])
    # keyword, no compression, no language, no translated keyword, then the text
    made = _chunk(b"iTXt", XMP + b"\0\0\0\0" + packet.encode("utf-8"))
    return b"".join([SIGNATURE, kept[0], made, *kept[1:]])
