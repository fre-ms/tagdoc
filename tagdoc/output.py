"""What a description leaves behind: the document with the description inside (a PDF: XMP
and the information dictionary in step; a picture: its XMP and EXIF, medRDS 7.4), or the
document as it came and a sidecar (``<file name>.xmp``, 7.5); and the configuration
document.

What the document's own metadata held beyond the standard stays (a PDF's mark of PDF/A
and its producer, a camera's data); what the standard defines is replaced.  A PDF carries
the configuration documents of the steps before it and tagdoc's own, no time, and a file
identifier made from them, so that the same input and document give the same bytes.  A
picture carries no configuration document: it lies beside it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pymupdf
from doccor import documents

from tagdoc import __version__, medrds
from tagdoc.errors import TagdocError
from tagdoc.project import EMBEDDED, SUFFIX, Described

_INFO = ("title", "author", "subject", "keywords", "creator", "producer", "creationDate",
         "modDate", "trapped")


def described_pdf(source: pymupdf.Document, meta: dict[str, Any], config: dict[str, Any]) -> bytes:
    """A copy of ``source`` with the description written into it."""
    doc = pymupdf.open("pdf", source.tobytes())
    try:
        doc.set_xml_metadata(medrds.merge_xmp(doc.get_xml_metadata() or None, meta))
        info = {k: v for k, v in doc.metadata.items() if k in _INFO and v}
        info.update(medrds.info_of(meta))
        made_with = f"tagdoc {__version__}"
        info.setdefault("producer", made_with)
        doc.set_metadata(info)
        if EMBEDDED in doc.embfile_names():
            doc.embfile_del(EMBEDDED)
        own = documents.document_bytes(config)
        documents.embed(doc, EMBEDDED, own, "tagdoc configuration: describes this PDF again")
        carried = [doc.embfile_get(name) for name in sorted(doc.embfile_names())
                   if name.endswith(".json") and name != EMBEDDED]
        # as doccor's finished_pdf, but the creator is the program the description names
        ident = hashlib.sha256(b"".join([*carried, own]) + made_with.encode()).hexdigest()
        doc.xref_set_key(-1, "ID", f"[<{ident[:32].upper()}><{ident[:32].upper()}>]")
        return doc.tobytes(garbage=3, deflate=True, no_new_id=True)
    finally:
        doc.close()


def write(described: Described, folder: str | Path, stem: str | None = None) -> dict[str, Path]:
    """Write the document under the ending it came with (``<stem>.pdf``, ``<stem>.jpg``
    …), the configuration document ``<stem>.tagdoc.json`` and, where the description goes
    into one, the sidecar ``<file name>.xmp`` into ``folder``; nothing anywhere else.
    Returns the paths by kind ("document": the described document; "config"; "sidecar"
    where there is one).  Raises "same-as-source", "unwritable"."""
    target = Path(folder)
    stem = stem or described.source.stem
    suffix = described.source.suffix
    name = f"{stem}{'.pdf' if suffix.lower() == '.pdf' else suffix}"
    paths = {"document": target / name, "config": target / f"{stem}{SUFFIX}"}
    if described.sidecar is not None:
        paths["sidecar"] = target / f"{name}.xmp"
    if paths["document"].resolve() == described.source.resolve():
        raise TagdocError("same-as-source")
    try:
        target.mkdir(parents=True, exist_ok=True)
        paths["document"].write_bytes(described.document)
        paths["config"].write_bytes(documents.document_bytes(described.config))
        if described.sidecar is not None:
            paths["sidecar"].write_bytes(described.sidecar.encode("utf-8"))
    except OSError as e:
        raise TagdocError("unwritable") from e
    return paths
