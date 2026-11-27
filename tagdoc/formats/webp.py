"""A WebP picture: its XMP in a chunk ``XMP ``, its EXIF in a chunk ``EXIF``, both named
in the header of the extended format (``VP8X``).  The picture's data are not touched: a
picture in the simple format gets the header of the extended one before them, which says
its size and what else the file holds.
"""

from __future__ import annotations

from tagdoc.formats.common import NoPlace

_ICC, _ALPHA, _EXIF, _XMP, _ANIMATION = 0x20, 0x10, 0x08, 0x04, 0x02


def is_webp(data: bytes) -> bool:
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def _chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    """The chunks of the file, as (name, payload)."""
    if not is_webp(data):
        raise NoPlace("not-webp")
    end = min(len(data), 8 + int.from_bytes(data[4:8], "little"))
    found = []
    at = 12
    while at + 8 <= end:
        size = int.from_bytes(data[at + 4:at + 8], "little")
        if at + 8 + size > len(data):
            raise NoPlace("not-webp")
        found.append((data[at:at + 4], data[at + 8:at + 8 + size]))
        at += 8 + size + (size & 1)  # a chunk of odd length is followed by a byte of padding
    if not found:
        raise NoPlace("not-webp")
    return found


def _chunk(name: bytes, payload: bytes) -> bytes:
    padding = b"\0" if len(payload) & 1 else b""
    return name + len(payload).to_bytes(4, "little") + payload + padding


def _extended(first: tuple[bytes, bytes]) -> bytes:
    """The header of the extended format for a picture in the simple one: its size, and
    whether it has transparency."""
    name, payload = first
    if name == b"VP8 ":
        if len(payload) < 10 or payload[3:6] != b"\x9d\x01\x2a":
            raise NoPlace("not-webp")
        width = int.from_bytes(payload[6:8], "little") & 0x3FFF
        height = int.from_bytes(payload[8:10], "little") & 0x3FFF
        flags = 0
    elif name == b"VP8L":
        if len(payload) < 5 or payload[0] != 0x2F:
            raise NoPlace("not-webp")
        bits = int.from_bytes(payload[1:5], "little")
        width, height = (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        flags = _ALPHA if (bits >> 28) & 1 else 0
    else:
        raise NoPlace("not-webp")
    if width < 1 or height < 1:
        raise NoPlace("not-webp")
    return bytes([flags, 0, 0, 0]) + (width - 1).to_bytes(3, "little") \
        + (height - 1).to_bytes(3, "little")


def exif_of(data: bytes) -> bytes | None:
    """The EXIF block of the picture (the TIFF structure), or None."""
    for name, payload in _chunks(data):
        if name == b"EXIF":
            return payload[6:] if payload[:6] == b"Exif\0\0" else payload
    return None


def written(data: bytes, packet: str | None, block: bytes | None) -> bytes:
    """The picture with ``packet`` as its XMP and ``block`` as its EXIF, each in place of
    what it had (None: what it had stays)."""
    chunks = _chunks(data)
    if chunks[0][0] != b"VP8X":
        chunks.insert(0, (b"VP8X", _extended(chunks[0])))
    header = bytearray(chunks[0][1])
    if len(header) < 10:
        raise NoPlace("not-webp")
    kept = [(name, payload) for name, payload in chunks[1:]
            if not (name == b"EXIF" and block is not None)
            and not (name == b"XMP " and packet is not None)]
    # after the picture's data: the EXIF, then the XMP, as the format orders them
    old_xmp = [c for c in kept if c[0] == b"XMP "]
    kept = [c for c in kept if c[0] != b"XMP "]
    if block is not None:
        kept.append((b"EXIF", block))
        header[0] |= _EXIF
    if packet is not None:
        kept.append((b"XMP ", packet.encode("utf-8")))
        header[0] |= _XMP
    kept += old_xmp
    body = b"WEBP" + _chunk(b"VP8X", bytes(header)) + b"".join(_chunk(n, p) for n, p in kept)
    if len(body) > 0xFFFFFFFF:
        raise NoPlace("too-long")
    return b"RIFF" + len(body).to_bytes(4, "little") + body
