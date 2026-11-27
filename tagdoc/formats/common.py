"""What the formats share: the reason a picture has no place for a description, and the
XMP packet found wherever it stands."""

from __future__ import annotations

_OPEN = b"<x:xmpmeta"
_CLOSE = b"</x:xmpmeta>"


class NoPlace(Exception):
    """The picture has no place for the description, or none tagdoc can write without
    risk: the description then goes into a sidecar (medRDS 7.5).  ``reason`` says why, in
    a word a caller can show."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def find_packet(data: bytes) -> str | None:
    """The XMP packet in a file as text, or None where the file holds none that can be
    seen; found wherever it stands, as the reference library finds it
    (``findXmpPacket``)."""
    start = data.find(_OPEN)
    if start < 0:
        return None
    end = data.find(_CLOSE, start)
    if end < 0:
        return None
    return data[start:end + len(_CLOSE)].decode("utf-8", errors="replace")
