"""The errors tagdoc reports: a fixed kind, the details its wording needs, and that
wording in English and German.  The kinds every tool of docrepro has, and those two tools
share, are worded alike (:mod:`doccor.errors`), so that one program can hold them all.  No
message quotes the content or the path of a document.
"""

from __future__ import annotations

from doccor import errors as _core
from doccor.errors import LANGUAGES, DocError, describe_error

_OWN: dict[str, dict[str, str]] = {
    "not-pdf": {  # worded as ocrdoc words it
        "en": "{tool} reads PDFs; optdoc makes one of a photo or an image first.",
        "de": "{tool} liest PDFs; aus einem Foto oder Bild macht optdoc zuerst eines.",
    },
    "bad-field": {
        "en": "The value given for {field} is not of its kind ({rule}).",
        "de": "Der Wert für {field} passt nicht ({rule}).",
    },
    "bad-card": {
        "en": "A card given is no vCard with a UID.",
        "de": "Eine angegebene Karte ist keine vCard mit UID.",
    },
}

_core.register(_OWN)
KINDS = _core.KINDS
__all__ = ["KINDS", "LANGUAGES", "DocError", "TagdocError", "describe_error"]


class TagdocError(DocError):
    """An error tagdoc can word for a person: its kind and the details the wording needs."""

    tool = "tagdoc"
