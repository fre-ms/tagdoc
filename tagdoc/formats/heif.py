"""A HEIC or HEIF picture: its XMP and its EXIF as items of the file, as the format has
them (an item of type ``mime`` with the content type ``application/rdf+xml``, and one of
type ``Exif``), each said to describe the picture.  The picture's data are not touched.

The file is a tree of boxes.  The one that lists the items (``meta``) stands before the
picture's data as a rule; an item more makes it longer, so the data move back, and every
place the list names moves with them.  What is written for an item is appended to the
file; the bytes of an item that is replaced are set to zero where nothing else lies in
them.

This is done only for a file whose list this module reads in full; for any other, and
for a sequence of pictures (a ``moov`` box), :class:`~tagdoc.formats.common.NoPlace` is
raised and the description goes into a sidecar.  The caller checks the result by looking
(:func:`same_picture`) before it trusts it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tagdoc.formats.common import NoPlace

XMP_TYPE = b"application/rdf+xml"
_WIDTHS = (0, 4, 8)


@dataclass
class _Box:
    kind: bytes
    start: int  # of the box
    body: int  # of its content, after its header
    end: int


@dataclass
class _Item:
    """Where an item's data lie: in the file (``method`` 0) or in the list's own data
    box (1), in one extent or several, each [index, offset, length], from ``base`` on."""

    ident: int
    method_field: int  # the two bytes that hold the method, as they came
    reference: int
    base: int
    extents: list[list[int]] = field(default_factory=list)

    @property
    def method(self) -> int:
        return self.method_field & 0x000F


@dataclass
class _Locations:
    """The box that says where every item's data lie (``iloc``)."""

    version: int
    flags: bytes
    offset_size: int
    length_size: int
    base_size: int
    index_size: int
    reserved: int  # the half byte that holds the index size from version 1 on
    items: list[_Item]


def _fail() -> NoPlace:
    return NoPlace("heif-structure")


def _boxes(data: bytes, start: int, end: int) -> list[_Box]:
    """The boxes between ``start`` and ``end``, which they must fill exactly."""
    found = []
    at = start
    while at < end:
        if at + 8 > end:
            raise _fail()
        size = int.from_bytes(data[at:at + 4], "big")
        body = at + 8
        if size == 1:
            if at + 16 > end:
                raise _fail()
            size = int.from_bytes(data[at + 8:at + 16], "big")
            body = at + 16
        elif size == 0:
            size = end - at  # to the end of what holds it
        if size < body - at or at + size > end:
            raise _fail()
        found.append(_Box(data[at + 4:at + 8], at, body, at + size))
        at += size
    return found


def _box(kind: bytes, payload: bytes) -> bytes:
    if len(payload) + 8 > 0xFFFFFFFF:
        raise _fail()
    return (len(payload) + 8).to_bytes(4, "big") + kind + payload


def is_heif(data: bytes) -> bool:
    return data[4:8] == b"ftyp"


def _number(data: bytes, at: int, width: int) -> int:
    if at + width > len(data):
        raise _fail()
    return int.from_bytes(data[at:at + width], "big")


def _locations(data: bytes, box: _Box) -> _Locations:
    at = box.body
    version, flags = _number(data, at, 1), data[at + 1:at + 4]
    if version > 2:
        raise _fail()
    sizes, more = _number(data, at + 4, 1), _number(data, at + 5, 1)
    found = _Locations(version, flags, sizes >> 4, sizes & 15, more >> 4,
                       more & 15 if version else 0, more & 15, [])
    if any(w not in _WIDTHS for w in (found.offset_size, found.length_size, found.base_size,
                                      found.index_size)):
        raise _fail()
    at += 6
    wide = 4 if version == 2 else 2
    count = _number(data, at, wide)
    at += wide
    for _ in range(count):
        ident = _number(data, at, wide)
        at += wide
        method = 0
        if version:
            method = _number(data, at, 2)
            at += 2
        reference = _number(data, at, 2)
        base = _number(data, at + 2, found.base_size)
        at += 2 + found.base_size
        extents = _number(data, at, 2)
        at += 2
        item = _Item(ident, method, reference, base)
        for _ in range(extents):
            index = _number(data, at, found.index_size)
            offset = _number(data, at + found.index_size, found.offset_size)
            length = _number(data, at + found.index_size + found.offset_size, found.length_size)
            at += found.index_size + found.offset_size + found.length_size
            item.extents.append([index, offset, length])
        found.items.append(item)
    if at != box.end:
        raise _fail()
    return found


def _written_locations(found: _Locations) -> bytes:
    wide = 4 if found.version == 2 else 2
    out = bytearray([found.version]) + found.flags
    out += bytes([found.offset_size << 4 | found.length_size,
                  found.base_size << 4 | (found.index_size if found.version else found.reserved)])
    out += len(found.items).to_bytes(wide, "big")
    for item in found.items:
        out += item.ident.to_bytes(wide, "big")
        if found.version:
            out += item.method_field.to_bytes(2, "big")
        out += item.reference.to_bytes(2, "big") + item.base.to_bytes(found.base_size, "big")
        out += len(item.extents).to_bytes(2, "big")
        for index, offset, length in item.extents:
            out += index.to_bytes(found.index_size, "big")
            out += offset.to_bytes(found.offset_size, "big")
            out += length.to_bytes(found.length_size, "big")
    return _box(b"iloc", bytes(out))


def _entries(data: bytes, box: _Box) -> tuple[int, list[tuple[int, bytes, bytes, _Box]]]:
    """The items the file lists (``iinf``): the version of the list, and each item's
    number, type and (for one of type ``mime``) content type, with its box."""
    version = _number(data, box.body, 1)
    wide = 2 if version == 0 else 4
    count = _number(data, box.body + 4, wide)
    boxes = _boxes(data, box.body + 4 + wide, box.end)
    if len(boxes) != count:
        raise _fail()
    found = []
    for entry in boxes:
        form = _number(data, entry.body, 1)
        if entry.kind != b"infe" or form not in (2, 3):
            raise _fail()  # an older entry names no type
        wide_id = 2 if form == 2 else 4
        ident = _number(data, entry.body + 4, wide_id)
        at = entry.body + 4 + wide_id + 2
        kind = data[at:at + 4]
        content = b""
        if kind == b"mime":
            name_end = data.find(b"\0", at + 4, entry.end)
            if name_end < 0:
                raise _fail()
            type_end = data.find(b"\0", name_end + 1, entry.end)
            content = data[name_end + 1:type_end if type_end >= 0 else entry.end]
        found.append((ident, kind, content, entry))
    return version, found


def _entry(ident: int, kind: bytes, content: bytes = b"") -> bytes:
    """An entry of the list for an item that is no picture to show (hidden)."""
    form = 2 if ident < 0x10000 else 3
    body = bytes([form, 0, 0, 1]) + ident.to_bytes(2 if form == 2 else 4, "big") + b"\0\0"
    body += kind + b"\0"  # no name
    if kind == b"mime":
        body += content + b"\0"
    return _box(b"infe", body)


@dataclass
class _File:
    """A file read as far as this module writes it."""

    data: bytes
    top: list[_Box]
    meta: _Box
    children: list[_Box]
    locations: _Locations
    list_version: int
    entries: list[tuple[int, bytes, bytes, _Box]]
    primary: int

    def child(self, kind: bytes) -> _Box | None:
        return next((box for box in self.children if box.kind == kind), None)

    def item(self, ident: int) -> _Item | None:
        return next((item for item in self.locations.items if item.ident == ident), None)

    def found(self, kind: bytes, content: bytes = b"") -> int | None:
        """The number of the first item of that type (and content type)."""
        return next((ident for ident, k, c, _box in self.entries
                     if k == kind and (kind != b"mime" or c == content)), None)

    def ranges(self, item: _Item) -> list[tuple[int, int, int]]:
        """Where an item's data lie, as (method, start, end): in the file for method 0,
        in the list's data box for method 1."""
        if item.method not in (0, 1) or item.reference != 0:
            raise _fail()
        return [(item.method, item.base + offset, item.base + offset + length)
                for _index, offset, length in item.extents]

    def bytes_of(self, item: _Item) -> bytes:
        """An item's data."""
        idat = self.child(b"idat")
        parts = []
        for method, start, end in self.ranges(item):
            if method == 1:
                if idat is None:
                    raise _fail()
                start, end = start + idat.body, end + idat.body
                if end > idat.end:
                    raise _fail()
            if end > len(self.data):
                raise _fail()
            parts.append(self.data[start:end])
        return b"".join(parts)


def _read(data: bytes) -> _File:
    if not is_heif(data):
        raise _fail()
    top = _boxes(data, 0, len(data))
    kinds = [box.kind for box in top]
    if b"moov" in kinds or kinds.count(b"meta") != 1:
        raise _fail()  # a sequence of pictures keeps places of its own
    meta = top[kinds.index(b"meta")]
    children = _boxes(data, meta.body + 4, meta.end)
    by_kind = {box.kind: box for box in children}
    listed = [box.kind for box in children]
    if not {b"iinf", b"iloc", b"pitm"} <= set(listed) \
            or any(listed.count(kind) > 1
                   for kind in (b"iinf", b"iloc", b"iref", b"pitm", b"idat")):
        raise _fail()
    pitm = by_kind[b"pitm"]
    primary = _number(data, pitm.body + 4, 2 if _number(data, pitm.body, 1) == 0 else 4)
    version, entries = _entries(data, by_kind[b"iinf"])
    return _File(data, top, meta, children, _locations(data, by_kind[b"iloc"]), version, entries,
                 primary)


def packet_of(data: bytes) -> bytes | None:
    """The XMP the file holds as an item, or None."""
    try:
        file = _read(data)
        ident = file.found(b"mime", XMP_TYPE)
        item = None if ident is None else file.item(ident)
        return None if item is None else file.bytes_of(item)
    except NoPlace:
        return None


def _exif_payload(file: _File) -> bytes | None:
    ident = file.found(b"Exif")
    item = None if ident is None else file.item(ident)
    return None if item is None else file.bytes_of(item)


def exif_of(data: bytes) -> bytes | None:
    """The EXIF block of the picture (the TIFF structure), or None."""
    try:
        payload = _exif_payload(_read(data))
    except NoPlace:
        return None
    if payload is None or len(payload) < 4:
        return None
    return payload[4 + int.from_bytes(payload[:4], "big"):] or None


def _reference(file: _File, added: list[int]) -> tuple[bytes, bool]:
    """The box of references (``iref``) with one more for each item added: that it
    describes the picture (``cdsc``).  Returns the box, and whether the file had one."""
    old = file.child(b"iref")
    if old is None:
        version = 0 if max([file.primary, *added]) < 0x10000 else 1
        body = bytes([version, 0, 0, 0])
    else:
        version = _number(file.data, old.body, 1)
        if version > 1:
            raise _fail()
        body = file.data[old.body:old.end]
    wide = 2 if version == 0 else 4
    for ident in added:
        if max(ident, file.primary) >= 1 << (8 * wide):
            raise _fail()
        body += _box(b"cdsc", ident.to_bytes(wide, "big") + (1).to_bytes(2, "big")
                     + file.primary.to_bytes(wide, "big"))
    return _box(b"iref", body), old is not None


def written(data: bytes, packet: str | None, block: bytes | None) -> bytes:
    """The picture with ``packet`` as its XMP item and ``block`` as its EXIF item, each
    in place of the item it had (None: what it had stays).  Raises :class:`NoPlace` for
    a file this module does not write."""
    file = _read(data)
    payloads: list[tuple[bytes, bytes, bytes]] = []  # type, content type, data
    if block is not None:
        old = _exif_payload(file)
        lead = old[:4 + int.from_bytes(old[:4], "big")] if old and len(old) >= 4 else bytes(4)
        payloads.append((b"Exif", b"", lead + block))
    if packet is not None:
        payloads.append((b"mime", XMP_TYPE, packet.encode("utf-8")))
    if not payloads:
        return data
    locations = file.locations
    if locations.length_size == 0 or (locations.offset_size == 0 and locations.base_size == 0):
        raise _fail()
    work = bytearray(data)
    idat = file.child(b"idat")
    taken = max([ident for ident, *_rest in file.entries]
                + [item.ident for item in locations.items] + [file.primary])
    added: list[int] = []
    new_entries = b""
    targets: list[_Item] = []
    for kind, content, _payload in payloads:
        ident = file.found(kind, content)
        item = None if ident is None else file.item(ident)
        if item is not None:  # replaced: what it held is set to zero, where it lies alone
            others = [r for other in locations.items if other is not item
                      for r in file.ranges(other)]
            for method, start, end in file.ranges(item):
                if any(m == method and a < end and start < b for m, a, b in others):
                    continue
                shift = 0
                if method == 1:
                    if idat is None:
                        raise _fail()
                    shift = idat.body
                work[start + shift:end + shift] = bytes(end - start)
            item.method_field &= ~0x000F  # its data lie in the file from now on
        else:
            taken += 1
            if taken >= (1 << 32 if locations.version == 2 else 1 << 16):
                raise _fail()
            item = _Item(taken, 0, 0, 0)
            locations.items.append(item)
            added.append(taken)
            new_entries += _entry(taken, kind, content)
        targets.append(item)
    # the list of items, and the references, with what was added
    entries_box = file.child(b"iinf")
    assert entries_box is not None
    wide = 2 if file.list_version == 0 else 4
    count = len(file.entries) + len(added)
    if count >= 1 << (8 * wide):
        raise _fail()
    head = entries_box.body
    new_list = _box(b"iinf", bytes(work[head:head + 4]) + count.to_bytes(wide, "big")
                    + bytes(work[head + 4 + wide:entries_box.end]) + new_entries)
    new_references, had_references = _reference(file, added) if added else (b"", True)

    def meta_with(locations_box: bytes) -> bytes:
        parts = [bytes(work[file.meta.body:file.meta.body + 4])]
        for child in file.children:
            if child.kind == b"iinf":
                parts.append(new_list)
            elif child.kind == b"iloc":
                parts.append(locations_box)
            elif child.kind == b"iref" and added:
                parts.append(new_references)
            else:
                parts.append(bytes(work[child.start:child.end]))
        if added and not had_references:
            parts.append(new_references)
        return _box(b"meta", b"".join(parts))

    # how much longer the list gets does not depend on the places it names
    for item in targets:
        item.reference, item.base = 0, 0
        item.extents = [[0, 0, 0]]
    grown = len(meta_with(_written_locations(locations))) - (file.meta.end - file.meta.start)
    last = file.top[-1]
    open_ended = int.from_bytes(data[last.start:last.start + 4], "big") == 0
    if open_ended and last.kind != b"mdat":
        raise _fail()  # what is appended would fall into a box that holds no data
    if any(length == 0 for item in locations.items if item.method == 0 and item not in targets
           for _index, _offset, length in item.extents):
        raise _fail()  # an item that reaches to the end of the file would take it in
    appended = bytearray()
    at = len(data) + grown
    for item, (_kind, _content, payload) in zip(targets, payloads, strict=True):
        if not open_ended:
            appended += (len(payload) + 8).to_bytes(4, "big") + b"mdat"
            at += 8
        place = at
        appended += payload
        at += len(payload)
        if locations.offset_size:
            item.extents = [[0, place, len(payload)]]
        else:
            item.base, item.extents = place, [[0, 0, len(payload)]]
    # what lay behind the list has moved back by as much as the list has grown
    for item in locations.items:
        if item in targets or item.method != 0 or item.reference != 0:
            continue
        places = [item.base + offset for _index, offset, _length in item.extents]
        if not places or all(place < file.meta.start for place in places):
            continue
        if not all(place >= file.meta.end for place in places):
            raise _fail()
        if item.base or not locations.offset_size:
            item.base += grown
        else:
            for extent in item.extents:
                extent[1] += grown
    limits = {name: 1 << (8 * size) for name, size in
              (("offset", locations.offset_size), ("length", locations.length_size),
               ("base", locations.base_size))}
    for item in locations.items:
        if item.base >= limits["base"] and (item.base or locations.base_size):
            raise _fail()
        for _index, offset, length in item.extents:
            if (offset >= limits["offset"] and (offset or locations.offset_size)) \
                    or length >= limits["length"]:
                raise _fail()
    new_meta = meta_with(_written_locations(locations))
    if len(new_meta) - (file.meta.end - file.meta.start) != grown:
        raise _fail()
    out = bytes(work[:file.meta.start]) + new_meta + bytes(work[file.meta.end:]) \
        + bytes(appended)
    if not same_items(data, out, payloads):
        raise _fail()
    return out


def same_items(before: bytes, after: bytes, written: list[tuple[bytes, bytes, bytes]]) -> bool:
    """True when ``after`` holds every item ``before`` held with the very bytes it held, but
    those replaced, and the items written (type, content type, bytes) with the bytes
    written; and the same boxes that say how the pictures are shown.  The standard's
    library checks the same (``sameItems``)."""
    try:
        a, b = _read(before), _read(after)
    except NoPlace:
        return False
    replaced = {a.found(kind, content) for kind, content, _data in written} - {None}
    try:
        for item in a.locations.items:
            if item.ident in replaced:
                continue
            other = b.item(item.ident)
            if other is None or a.bytes_of(item) != b.bytes_of(other):
                return False
        for kind, content, data in written:
            ident = b.found(kind, content)
            made = None if ident is None else b.item(ident)
            if made is None or b.bytes_of(made) != data:
                return False
    except NoPlace:
        return False

    def shown(file: _File) -> list[bytes]:
        return [file.data[c.start:c.end] for c in file.children if c.kind in (b"iprp", b"pitm")]

    return a.primary == b.primary and shown(a) == shown(b)


def same_picture(old: bytes, new: bytes, packet: str | None, block: bytes | None) -> bool:
    """True when ``new`` shows the very pictures ``old`` shows, pixel for pixel, and a
    reader that knows the format (libheif) finds the XMP and the EXIF in it that were to
    be written.  Raises :class:`NoPlace` where that reader (pillow-heif) is not installed:
    what cannot be checked is not written."""
    try:
        import pillow_heif
    except ImportError as e:
        raise NoPlace("needs-pillow-heif") from e
    try:
        before, after = pillow_heif.open_heif(old), pillow_heif.open_heif(new)
        if len(before) != len(after):
            return False
        for a, b in zip(before, after, strict=True):
            if (a.size, a.mode) != (b.size, b.mode) or bytes(a.data) != bytes(b.data):
                return False
        said = after.info  # of the picture the file names as its first
        if packet is not None and packet.encode("utf-8") not in bytes(said.get("xmp") or b""):
            return False
        return block is None or bytes(said.get("exif") or b"").endswith(block)
    except Exception:  # whatever the reader makes of a file it cannot read: not the same
        return False
