"""A GIF: its XMP in an application extension ``XMP Data``, as XMP defines it for GIF
(the packet as it is, followed by a trailer that lets a program which does not know XMP
step over it).  A GIF has no EXIF.  The picture's data are not touched; a file that calls
itself GIF87a is called GIF89a, since only that version has extensions.
"""

from __future__ import annotations

from tagdoc.formats.common import NoPlace

_APPLICATION = b"\x21\xff\x0bXMP DataXMP"
# what follows the packet: read as sub-blocks from wherever a program lands in it, it
# always ends at the terminator
_TRAILER = b"\x01" + bytes(range(255, -1, -1)) + b"\0"


def is_gif(data: bytes) -> bool:
    return data[:6] in (b"GIF87a", b"GIF89a")


def _sub_blocks(data: bytes, at: int) -> int:
    """Where the sub-blocks beginning at ``at`` end (after their terminator)."""
    while True:
        if at >= len(data):
            raise NoPlace("not-gif")
        size = data[at]
        at += 1 + size
        if size == 0:
            return at


def _blocks(data: bytes) -> tuple[list[tuple[int, int]], int]:
    """The XMP extensions of the file, as (start, end), and where its trailer stands."""
    if not is_gif(data) or len(data) < 13:
        raise NoPlace("not-gif")
    at = 13
    if data[10] & 0x80:
        at += 3 * (2 << (data[10] & 7))  # the global colour table
    xmp: list[tuple[int, int]] = []
    while True:
        if at >= len(data):
            raise NoPlace("not-gif")
        kind = data[at]
        if kind == 0x3B:
            return xmp, at
        if kind == 0x2C:  # a picture: its descriptor, its colours, its data
            if at + 10 > len(data):
                raise NoPlace("not-gif")
            packed = data[at + 9]
            at += 10
            if packed & 0x80:
                at += 3 * (2 << (packed & 7))
            at = _sub_blocks(data, at + 1)
        elif kind == 0x21:  # an extension
            start = at
            at = _sub_blocks(data, at + 2)
            if data[start:start + len(_APPLICATION)] == _APPLICATION:
                xmp.append((start, at))
        else:
            raise NoPlace("not-gif")


def with_packet(data: bytes, packet: str) -> bytes:
    """The picture with ``packet`` as its XMP, in place of any XMP it had, before the
    file's trailer."""
    old, trailer = _blocks(data)
    made = _APPLICATION + packet.encode("utf-8") + _TRAILER
    parts = []
    at = 6
    for start, end in old:
        parts.append(data[at:start])
        at = end
    parts.append(data[at:trailer])
    return b"GIF89a" + b"".join(parts) + made + data[trailer:]
