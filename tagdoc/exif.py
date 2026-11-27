"""The EXIF of a picture, as far as tagdoc reads and writes it.

EXIF is a TIFF structure: a header, then directories of entries, the first of which says
what the picture is (its description, who made it, the camera and its program).  The same
structure is the EXIF block of a JPEG, a PNG, a WebP and a HEIC picture, and a TIFF file
is one as a whole; so this one module reads and writes them all.

**Nothing in the structure moves.**  Everything else in it stays where it is, byte for
byte (a camera's own notes point at their place in the block and would break if it
shifted).  A value is written where the old one stood when it fits there; else it is
appended, and where an entry is added a new first directory is appended as well and the
header points at it.

**What is replaced is gone.**  The bytes of a value that is replaced or taken away are
set to zero, when nothing else in the structure points at them, so that a description a
person corrected does not stay in the file where no program shows it.

Text is written as UTF-8 in the type EXIF calls ASCII, as most programs write and read it
(an umlaut in a name would otherwise be lost); it is read as UTF-8, else as Latin-1.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

DESCRIPTION, MAKE, MODEL, SOFTWARE, ARTIST = 270, 271, 272, 305, 315
XMP = 700  # the XMP packet of a TIFF file
TEXT = (DESCRIPTION, MAKE, MODEL, SOFTWARE, ARTIST)
BYTE, ASCII, UTF8 = 1, 2, 129
# bytes of one value of each type
_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 13: 4,
          129: 1}
# the entries that point at a directory of their own (EXIF details, the place, …)
_DIRECTORIES = (0x8769, 0x8825, 0xA005, 0x014A)
# offsets and byte counts of the picture's own data (strips, tiles, an embedded preview)
_DATA = ((273, 279), (324, 325), (513, 514))
_LIMIT = 64  # directories followed at most: a structure that goes round in circles ends


class NotExif(Exception):
    """What was given is no TIFF structure this module can read (or a BigTIFF)."""


@dataclass
class _Entry:
    tag: int
    kind: int
    count: int
    raw: bytes  # the four bytes of the value, or of its offset

    @property
    def size(self) -> int:
        return _SIZES.get(self.kind, 1) * self.count


def _order(block: bytes) -> str:
    """The byte order of the structure, as :mod:`struct` names it."""
    if len(block) < 8 or block[:2] not in (b"II", b"MM"):
        raise NotExif
    order = "<" if block[:2] == b"II" else ">"
    if struct.unpack_from(order + "H", block, 2)[0] != 42:
        raise NotExif  # 43 is BigTIFF, with offsets of eight bytes
    return order


def _directory(block: bytes, at: int, order: str) -> tuple[list[_Entry], int]:
    """The entries of the directory at ``at``, and where the next directory stands (0:
    there is none)."""
    if at < 8 or at + 2 > len(block):
        raise NotExif
    count = struct.unpack_from(order + "H", block, at)[0]
    end = at + 2 + 12 * count
    if end + 4 > len(block):
        raise NotExif
    entries = []
    for k in range(count):
        tag, kind, number = struct.unpack_from(order + "HHI", block, at + 2 + 12 * k)
        entries.append(_Entry(tag, kind, number, block[at + 10 + 12 * k:at + 14 + 12 * k]))
    return entries, struct.unpack_from(order + "I", block, end)[0]


def _where(entry: _Entry, order: str) -> int | None:
    """Where the value of an entry stands in the block, or None when it is held in the
    entry itself (four bytes at most)."""
    return None if entry.size <= 4 else struct.unpack(order + "I", entry.raw)[0]


def _value(block: bytes, entry: _Entry, order: str) -> bytes:
    at = _where(entry, order)
    if at is None:
        return entry.raw[:entry.size]
    if at + entry.size > len(block):
        raise NotExif
    return block[at:at + entry.size]


def _text(data: bytes) -> str:
    data = data.split(b"\0", 1)[0]
    try:
        return data.decode("utf-8").strip()
    except UnicodeDecodeError:
        return data.decode("latin-1").strip()


def read(block: bytes) -> dict[int, str]:
    """The texts of the first directory tagdoc knows, by tag (:data:`TEXT`); those that
    are empty are left out.  Raises :class:`NotExif`."""
    order = _order(block)
    entries, _next = _directory(block, struct.unpack_from(order + "I", block, 4)[0], order)
    found = {}
    for entry in entries:
        if entry.tag in TEXT and entry.kind in (ASCII, UTF8):
            text = _text(_value(block, entry, order))
            if text:
                found[entry.tag] = text
    return found


def packet(block: bytes) -> bytes | None:
    """The XMP packet a TIFF file names in its first directory (tag 700), or None."""
    order = _order(block)
    entries, _next = _directory(block, struct.unpack_from(order + "I", block, 4)[0], order)
    for entry in entries:
        if entry.tag == XMP:
            return _value(block, entry, order)
    return None


def as_text(text: str) -> tuple[int, bytes]:
    """A text as the value of an entry: its type and bytes."""
    return ASCII, text.encode("utf-8") + b"\0"


def _used(block: bytes, order: str) -> list[tuple[int, int, int, int]]:
    """Every place of the block something points at: the values the entries keep
    outside themselves and the picture's own data, as (start, end, tag, the directory
    the entry stands in), through every directory that can be reached.  Raises
    :class:`NotExif` where the structure cannot be followed, which then means: wipe
    nothing."""
    used: list[tuple[int, int, int, int]] = []
    waiting = [struct.unpack_from(order + "I", block, 4)[0]]
    seen: set[int] = set()
    while waiting:
        at = waiting.pop()
        if at == 0 or at in seen:
            continue
        seen.add(at)
        if len(seen) > _LIMIT:
            raise NotExif
        entries, following = _directory(block, at, order)
        waiting.append(following)
        by_tag = {entry.tag: entry for entry in entries}
        for entry in entries:
            place = _where(entry, order)
            if place is not None:
                used.append((place, place + entry.size, entry.tag, at))
            if entry.tag in _DIRECTORIES and entry.kind in (4, 13):
                data = _value(block, entry, order)
                waiting += [struct.unpack_from(order + "I", data, 4 * k)[0]
                            for k in range(entry.count)]
        for offsets, lengths in _DATA:
            if offsets in by_tag and lengths in by_tag:
                starts = _numbers(block, by_tag[offsets], order)
                sizes = _numbers(block, by_tag[lengths], order)
                used += [(start, start + size, offsets, at)
                         for start, size in zip(starts, sizes, strict=False)]
    return used


def _numbers(block: bytes, entry: _Entry, order: str) -> list[int]:
    """The values of an entry of whole numbers (SHORT or LONG)."""
    data = _value(block, entry, order)
    code = {3: "H", 4: "I", 13: "I"}.get(entry.kind)
    if code is None:
        raise NotExif
    return list(struct.unpack_from(f"{order}{entry.count}{code}", data))


def _wipe(block: bytearray, start: int, end: int, tag: int, order: str) -> None:
    """Set the bytes of a value of the first directory that is gone to zero, unless
    something else in the structure points at them (or the structure cannot be followed
    to be sure)."""
    try:
        first = struct.unpack_from(order + "I", block, 4)[0]
        others = [(a, b) for a, b, t, directory in _used(bytes(block), order)
                  if not (t == tag and directory == first)]
    except (NotExif, struct.error):
        return
    if any(a < end and start < b for a, b in others):
        return
    block[start:end] = bytes(end - start)


def changed(block: bytes, changes: dict[int, tuple[int, bytes] | None]) -> bytes:
    """The structure with entries of its first directory set (to a type and its bytes) or
    taken away (None); see the module for what stays and what goes.  The same block and
    changes give the same bytes.  Raises :class:`NotExif`."""
    order = _order(block)
    out = bytearray(block)
    first = struct.unpack_from(order + "I", out, 4)[0]
    entries, following = _directory(bytes(out), first, order)
    held = {entry.tag: entry for entry in entries}
    rewritten = False  # the directory itself has to be written anew (an entry more or fewer)
    for tag in sorted(changes):
        change = changes[tag]
        old = held.get(tag)
        if change is None and old is None:
            continue
        if old is not None:
            place = _where(old, order)
            if change is not None and change[0] == old.kind and place is not None \
                    and 4 < len(change[1]) <= old.size:
                # it fits where the old value stood: written there, the rest set to zero
                out[place:place + old.size] = change[1] + bytes(old.size - len(change[1]))
                old.count = len(change[1]) // _SIZES.get(old.kind, 1)
                continue
            if change is not None and change[0] == old.kind and place is None \
                    and len(change[1]) == old.size:
                old.raw = change[1] + bytes(4 - len(change[1]))  # as short as the old one
                continue
            if place is not None:
                _wipe(out, place, place + old.size, tag, order)
        if change is None:
            del held[tag]
            rewritten = True
            continue
        kind, data = change
        count = len(data) // _SIZES.get(kind, 1)
        if len(data) <= 4:
            raw = data + bytes(4 - len(data))
        else:
            if len(out) % 2:
                out.append(0)  # a value begins on an even byte
            raw = struct.pack(order + "I", len(out))
            out += data
        rewritten = rewritten or old is None
        held[tag] = _Entry(tag, kind, count, raw)
    listed = sorted(held.values(), key=lambda entry: entry.tag)
    table = struct.pack(order + "H", len(listed)) + b"".join(
        struct.pack(order + "HHI", entry.tag, entry.kind, entry.count) + entry.raw
        for entry in listed) + struct.pack(order + "I", following)
    if not rewritten:
        out[first:first + len(table)] = table  # the same entries: in their place
    elif len(listed) <= len(entries):
        # fewer entries: in the place of the old directory, what is left of it set to zero
        old_length = 2 + 12 * len(entries) + 4
        out[first:first + old_length] = table + bytes(old_length - len(table))
    else:
        out[first:first + 2 + 12 * len(entries) + 4] = bytes(2 + 12 * len(entries) + 4)
        if len(out) % 2:
            out.append(0)
        struct.pack_into(order + "I", out, 4, len(out))
        out += table
    if len(out) > 0xFFFFFFFF:
        raise NotExif
    return bytes(out)


def new(changes: dict[int, tuple[int, bytes] | None]) -> bytes | None:
    """A structure that holds nothing but the entries given (None where none has a
    value): for a picture that has no EXIF yet."""
    if not any(change is not None for change in changes.values()):
        return None
    empty = b"II*\0" + struct.pack("<I", 8) + struct.pack("<H", 0) + struct.pack("<I", 0)
    return changed(empty, changes)


__all__ = ["ARTIST", "ASCII", "BYTE", "DESCRIPTION", "MAKE", "MODEL", "SOFTWARE", "TEXT", "XMP",
           "NotExif", "as_text", "changed", "new", "packet", "read"]
