"""Where each kind of picture keeps a description, and writing it there.

tagdoc writes a description into a picture where the picture's format has a place for
it, and leaves the picture's own data untouched (medRDS 7.4):

=========  =======================================  ==================================
picture    XMP                                      EXIF, in step with it
=========  =======================================  ==================================
JPEG       an APP1 segment                          the EXIF segment
PNG        the chunk ``iTXt`` ``XML:com.adobe.xmp``  the chunk ``eXIf``
TIFF       entry 700 of the first directory         entries 270 and 315 of it
WebP       the chunk ``XMP``                        the chunk ``EXIF``
HEIC/HEIF  an item ``application/rdf+xml``          the item ``Exif``
GIF        the application extension ``XMP Data``   (a GIF has none)
BMP, PNM   no place: a sidecar (7.5)
=========  =======================================  ==================================

"In step" are the two texts EXIF has for what a description says: ``ImageDescription``
(the description) and ``Artist`` (the names of the authors).  Everything else a picture's
EXIF and XMP hold stays (the camera, the moment, the place); the two texts are replaced,
and taken away where the description has none (:mod:`tagdoc.exif`).

Reading is the other half: what a picture says of itself already, its XMP packet
wherever it stands and the texts of its EXIF (:func:`held`).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from tagdoc import exif
from tagdoc.formats import gif, heif, jpeg, png, tiff, webp
from tagdoc.formats.common import NoPlace, find_packet

JPEG, PNG, TIFF, WEBP, GIF, HEIF = "jpeg", "png", "tiff", "webp", "gif", "heif"
FORMATS = {".jpg": JPEG, ".jpeg": JPEG, ".png": PNG, ".tif": TIFF, ".tiff": TIFF, ".webp": WEBP,
           ".gif": GIF, ".heic": HEIF, ".heif": HEIF}
# what each format has a place for
PLACES: dict[str, tuple[str, ...]] = {JPEG: ("xmp", "exif"), PNG: ("xmp", "exif"),
                                      TIFF: ("xmp", "exif"), WEBP: ("xmp", "exif"),
                                      HEIF: ("xmp", "exif"), GIF: ("xmp",)}
_IS = {JPEG: jpeg.is_jpeg, PNG: png.is_png, TIFF: tiff.is_tiff, WEBP: webp.is_webp,
       GIF: gif.is_gif, HEIF: heif.is_heif}


def genuine(data: bytes, suffix: str) -> bool:
    """True when a file begins as a picture of the type its name says does."""
    form = FORMATS.get(suffix.lower())
    if form is not None:
        return bool(_IS[form](data))
    if suffix.lower() == ".bmp":
        return data[:2] == b"BM"
    return suffix.lower() == ".pnm" and data[:1] == b"P" and data[1:2] in b"1234567"


def places(suffix: str) -> tuple[str, ...]:
    """What a picture of that type has a place for: "xmp", "exif"; nothing for a type
    whose description goes into a sidecar."""
    return PLACES.get(FORMATS.get(suffix.lower(), ""), ())


@dataclass
class Held:
    """What a picture says of itself: its XMP packet (None without one), the texts of its
    EXIF by tag (:data:`tagdoc.exif.TEXT`), and when it was taken, as its EXIF says (ISO
    8601; None where it says nothing)."""

    packet: str | None = None
    texts: dict[int, str] = field(default_factory=dict)
    taken: str | None = None


def packet_of(data: bytes, suffix: str) -> str | None:
    """The XMP packet of a picture as text, where its format keeps it (a TIFF's entry 700,
    a HEIC's item), else wherever it stands; as the standard's library reads it."""
    form = FORMATS.get(suffix.lower())
    found: bytes | None = None
    if form == TIFF and tiff.is_tiff(data):
        try:
            found = exif.packet(data)
        except (exif.NotExif, ValueError, IndexError, struct.error):
            found = None
    elif form == HEIF:
        found = heif.packet_of(data)
    if found:
        return found.decode("utf-8", errors="replace")
    return find_packet(data)


def _block(data: bytes, form: str) -> bytes | None:
    """The EXIF block of a picture, or None (for a TIFF: the file itself)."""
    if form == JPEG:
        return jpeg.exif_of(data)
    if form == PNG:
        return png.exif_of(data)
    if form == WEBP:
        return webp.exif_of(data)
    if form == HEIF:
        return heif.exif_of(data)
    return data if form == TIFF else None


def held(data: bytes, suffix: str) -> Held:
    """What the picture says of itself; nothing for what is no picture of its type."""
    form = FORMATS.get(suffix.lower())
    found = Held(packet_of(data, suffix))
    if form is None or not _IS[form](data):
        return found
    try:
        block = _block(data, form)
        if block is not None:
            found.texts = exif.read(block)
            found.taken = exif.taken(block)
    except (NoPlace, exif.NotExif, ValueError, IndexError, struct.error):
        found.texts, found.taken = {}, None
    return found


def written(data: bytes, suffix: str, packet: str,
            texts: dict[int, str | None]) -> tuple[bytes, tuple[str, ...]]:
    """The picture with ``packet`` as its XMP and its EXIF in step with ``texts`` (by
    tag; None: the picture is to say nothing there).  Returns the picture and where the
    description stands in it: "xmp", and "exif" where its EXIF says one of the texts.  The
    picture's own data are the same, byte for byte; the same picture, packet and texts
    give the same bytes.

    Raises :class:`NoPlace` where the description cannot go into the picture: a type
    without a place, a file that is not what its name says, a packet too long for a JPEG,
    a HEIC file that cannot be written safely or checked."""
    form = FORMATS.get(suffix.lower())
    if form is None:
        raise NoPlace("no-place")
    if not _IS[form](data):
        raise NoPlace("not-" + form)
    changes = {tag: (exif.as_text(text) if text else None) for tag, text in texts.items()}
    both = ("xmp", "exif") if any(texts.values()) else ("xmp",)
    try:
        if form == TIFF:
            return tiff.written(data, packet, changes), both
        if form == GIF:
            return gif.with_packet(data, packet), ("xmp",)
        old = _block(data, form)
        try:
            block = exif.new(changes) if old is None else exif.changed(old, changes)
        except (exif.NotExif, ValueError, IndexError):
            block, both = None, ("xmp",)  # an EXIF block that cannot be followed stays
        if block == old:
            block = None  # it is in step already
        if form == JPEG:
            out = data
            if block is not None:
                try:
                    out = jpeg.with_exif(data, block)
                except NoPlace:  # too long for a segment: the XMP says it all the same
                    both = ("xmp",)
            return jpeg.with_packet(out, packet), both
        if form == PNG:
            out = png.with_exif(data, block) if block is not None else data
            return png.with_packet(out, packet), both
        if form == WEBP:
            return webp.written(data, packet, block), both
        out = heif.written(data, packet, block)
        if not heif.same_picture(data, out, packet, block):
            raise NoPlace("heif-unchecked")
        return out, both
    except NoPlace:
        raise
    except (ValueError, IndexError, OverflowError) as e:  # a file that is not what it seems
        raise NoPlace("not-" + form) from e


__all__ = ["FORMATS", "PLACES", "Held", "NoPlace", "find_packet", "genuine", "held", "packet_of",
           "places", "written"]
