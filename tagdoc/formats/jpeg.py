"""A JPEG: its XMP in an APP1 segment, its EXIF in another (medRDS 7.4).  The picture's
data are not touched; segments are put in, taken out or replaced before them.

The XMP is written exactly as the standard's reference library writes it
(``embedXmpJpeg``): the same bytes for the same picture and packet.
"""

from __future__ import annotations

from tagdoc.formats.common import NoPlace

XMP = b"http://ns.adobe.com/xap/1.0/\0"
EXIF = b"Exif\0\0"
_ALONE = (0x01, *range(0xD0, 0xD8))  # markers that stand alone, without a length


def is_jpeg(data: bytes) -> bool:
    return data[:2] == b"\xff\xd8"


def _segments(data: bytes) -> list[tuple[int, int, int]]:
    """The segments before the picture's data, as (marker, start, end); the scan data
    and what follows them are no segments here."""
    found = []
    at = 2
    while at + 4 <= len(data) and data[at] == 0xFF:
        marker = data[at + 1]
        if marker == 0xFF:  # a fill byte
            at += 1
            continue
        if marker in _ALONE:
            at += 2
            continue
        if marker in (0xDA, 0xD9):  # the scan begins, or the picture ends
            break
        end = at + 2 + int.from_bytes(data[at + 2:at + 4], "big")
        if end > len(data):
            break
        found.append((marker, at, end))
        at = end
    return found


def exif_of(data: bytes) -> bytes | None:
    """The EXIF block of the picture (the TIFF structure), or None."""
    for marker, start, end in _segments(data):
        if marker == 0xE1 and data[start + 4:start + 10] == EXIF:
            return data[start + 10:end]
    return None


def with_exif(data: bytes, block: bytes) -> bytes:
    """The picture with ``block`` as its EXIF: in the place of the block it had, else
    right after the JFIF segments at its start.  Raises :class:`NoPlace` for a block too
    long for a segment."""
    length = len(block) + len(EXIF) + 2
    if length > 0xFFFF:
        raise NoPlace("exif-too-long")
    segment = b"\xff\xe1" + length.to_bytes(2, "big") + EXIF + block
    at = 2
    for marker, start, end in _segments(data):
        if marker == 0xE1 and data[start + 4:start + 10] == EXIF:
            return data[:start] + segment + data[end:]
        if marker == 0xE0 and start == at:
            at = end  # the JFIF segments lead
    return data[:at] + segment + data[at:]


def with_packet(data: bytes, packet: str) -> bytes:
    """The picture with ``packet`` as its XMP, in place of any XMP it had; the reference
    library's ``embedXmpJpeg``, byte for byte.  Raises :class:`NoPlace` for a packet too
    long for a segment."""
    if not is_jpeg(data):
        raise NoPlace("not-jpeg")
    payload = packet.encode("utf-8")
    length = len(payload) + len(XMP) + 2
    if length > 0xFFFF:
        raise NoPlace("xmp-too-long")
    # the segments before the picture: APP0 and Exif stay in front, an old XMP segment goes
    kept: list[bytes] = []
    later: list[bytes] = []
    at = 2
    while at + 4 <= len(data) and data[at] == 0xFF and 0xE0 <= data[at + 1] <= 0xEF:
        size = int.from_bytes(data[at + 2:at + 4], "big")
        segment = data[at:at + 2 + size]
        is_xmp = data[at + 1] == 0xE1 and data[at + 4:at + 4 + len(XMP)] == XMP
        leads = data[at + 1] == 0xE0 or (data[at + 1] == 0xE1 and not later)
        if not is_xmp:
            (kept if leads else later).append(segment)
        at += 2 + size
    head = b"\xff\xe1" + length.to_bytes(2, "big")
    return b"".join([data[:2], *kept, head, XMP, payload, *later, data[at:]])
