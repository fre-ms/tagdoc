"""A TIFF file: its XMP in the entry 700 of its first directory, its description and who
made it in the entries the format has for them (270, 315): a TIFF is an EXIF structure as
a whole (:mod:`tagdoc.exif`).  Nothing in the file moves, the picture's data least of all.
A BigTIFF (a file of more than four gigabytes) is not written.
"""

from __future__ import annotations

from tagdoc import exif
from tagdoc.formats.common import NoPlace


def is_tiff(data: bytes) -> bool:
    return data[:4] in (b"II*\0", b"MM\0*")


def texts_of(data: bytes) -> dict[int, str]:
    """What the file's first directory says in words (:data:`tagdoc.exif.TEXT`)."""
    try:
        return exif.read(data)
    except (exif.NotExif, ValueError):
        return {}


def written(data: bytes, packet: str, changes: dict[int, tuple[int, bytes] | None]) -> bytes:
    """The file with ``packet`` as its XMP and the entries of ``changes`` set or taken
    away.  Raises :class:`NoPlace` for a file that is no TIFF this module writes."""
    try:
        return exif.changed(data, {**changes, exif.XMP: (exif.BYTE, packet.encode("utf-8"))})
    except (exif.NotExif, ValueError, IndexError) as e:
        raise NoPlace("not-tiff") from e
