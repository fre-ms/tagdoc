"""The description of one document, and its configuration document.

A project holds what tagdoc writes about a document: every field of :mod:`tagdoc.medrds`
with its value and who decided it ("auto": tagdoc's suggestion, "person"), and the copies
of the cards the people it names are named with.  Its configuration document
(``<stem>.tagdoc.json``, format ``tagdoc-config``) is that, and nothing else (no paths, no
times):

- **Reproducing.**  The input and the document give the same result, byte for byte.
- **Resuming.**  The window saves the document and opens it again where the person stopped;
  the PDF tagdoc writes carries it too (``tagdoc.json``).
- **Going on after an earlier step changed.**  A description is of the whole document, not
  of a page: when the input changed (optdoc or ocrdoc made it anew), every field a person
  decided stays, and tagdoc's own suggestions are made again from the new text
  (:attr:`Project.rebased`).

A PDF signed or time-stamped by someone else must stay as it is (medRDS 7.5): its
description goes into a sidecar, as it does where the person asks for one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymupdf
from doccor import documents
from doccor.errors import DocError

from tagdoc import __version__, describe, medrds
from tagdoc.errors import TagdocError

FORMAT = "tagdoc-config"
FORMAT_VERSION = 1
SUFFIX = ".tagdoc.json"
EMBEDDED = "tagdoc.json"
_LANGUAGE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
# the rule of each field, for its check and for the message that it is broken
RULES: dict[str, str] = {
    "title": "a text", "kind": "a kind of medRDS (tagdoc about)",
    "typeCode": "system|code, as http://loinc.org|11502-2",
    "creator": "people named as medRDS 7.2 says", "institution": "bodies named as 7.2 says",
    "authenticator": "a person named as 7.2 says", "description": "a text",
    "subject": "keywords", "language": "BCP 47 tags, as de or en-GB", "source": "a text",
    "creatorTool": "a text", "date": "ISO 8601: 2026-03-12, or with time and offset",
    "confidentiality": "N, R or V", "cards": "vCards with a UID",
}


@dataclass
class Options:
    """The settings: the description into a sidecar rather than into the PDF
    (``sidecar``), and the program the document is made with (``creator_tool``; docrepro
    gives its own; else tagdoc suggests what the PDF names)."""

    sidecar: bool = False
    creator_tool: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: Any) -> Options:
        if not isinstance(d, dict):
            raise TagdocError("bad-config", reason="field")
        options = cls()
        for name, kinds in (("sidecar", (bool,)), ("creator_tool", (str, type(None)))):
            if name in d:
                if not isinstance(d[name], kinds):
                    raise TagdocError("bad-config", reason="field")
                setattr(options, name, d[name])
        return options


def _fits(name: str, value: Any) -> bool:
    """True when ``value`` is of the kind of the field ``name`` (None: no value)."""
    if value is None:
        return True
    if name in medrds.LISTS:
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
            return False
        if name == "language":
            return all(_LANGUAGE.match(v) for v in value)
        if name == "typeCode":
            return all("|" in v for v in value)
        if name == "cards":
            return all(medrds.is_card(v) and medrds.uid_of_card(v) for v in value)
        return True
    if not isinstance(value, str) or not value.strip():
        return False
    if name == "kind":
        return value in medrds.kinds()
    if name == "date":
        return medrds.pdf_date(value) is not None
    if name == "confidentiality":
        return value in medrds.CONFIDENTIALITY
    return True


def check(name: str, value: Any) -> Any:
    """``value`` for the field ``name``, or the error "bad-field" naming its rule."""
    if name not in medrds.FIELDS:
        raise TagdocError("bad-field", field=name, rule="no field of tagdoc")
    if not _fits(name, value):
        raise TagdocError("bad-field", field=name, rule=RULES[name])
    return value


def load_config(path: str | Path) -> dict[str, Any]:
    """A configuration document from its file, or from the PDF tagdoc wrote."""
    try:
        return documents.load_document(path, FORMAT, FORMAT_VERSION, EMBEDDED, "tagdoc")
    except DocError as e:
        reason = e.details.get("reason")
        raise (TagdocError(e.kind, reason=reason) if reason is not None
               else TagdocError(e.kind)) from e


@dataclass
class Described:
    """The result: the PDF as tagdoc gives it (with the description inside, or as it came
    where the description goes into a sidecar), the sidecar's packet (None without one),
    the configuration document, and what is still missing or wrong."""

    source: Path
    pdf: bytes
    sidecar: str | None
    config: dict[str, Any]
    problems: list[dict[str, str]] = field(default_factory=list)


class Project:
    """The description of one PDF; see the module."""

    def __init__(self, source: Path, doc: pymupdf.Document, sha256: str, size: int,
                 options: Options) -> None:
        self.source = source
        self.doc = doc
        self.sha256 = sha256
        self.size = size
        self.options = options
        self.decided: dict[str, Any] = {}  # a person's values, by field
        self._suggested: dict[str, Any] | None = None
        self.rebased = False

    @classmethod
    def open(cls, source: str | Path, options: Options | None = None,
             config: dict[str, Any] | None = None) -> Project:
        """A project on a PDF: fresh, or as ``config`` left it.  Raises "missing",
        "not-pdf", "unreadable", "encrypted", "bad-config"."""
        source = Path(source)
        if not source.is_file():
            raise TagdocError("missing")
        if source.suffix.lower() != ".pdf":
            raise TagdocError("not-pdf")
        try:
            doc = pymupdf.open(source)
        except Exception as e:  # MuPDF words its failures with the file's name
            raise TagdocError("unreadable") from e
        if doc.needs_pass:
            doc.close()
            raise TagdocError("encrypted")
        if config is not None:
            options = Options.from_dict(config.get("options", {}))
        project = cls(source, doc, documents.digest(source), source.stat().st_size,
                      options or Options())
        if config is not None:
            try:
                project._take(config)
            except Exception:
                project.close()
                raise
        return project

    def _take(self, config: dict[str, Any]) -> None:
        """The fields of a configuration document: all of them for the same input; for
        another, a person's alone (the rest is suggested again)."""
        named = config.get("input")
        fields = config.get("fields")
        if not isinstance(named, dict) or not isinstance(fields, dict):
            raise TagdocError("bad-config", reason="field")
        same = named.get("sha256") == self.sha256
        self.rebased = not same
        suggested: dict[str, Any] = {}
        for name, entry in fields.items():
            if name not in medrds.FIELDS or not isinstance(entry, dict) \
                    or entry.get("by") not in ("auto", "person"):
                raise TagdocError("bad-config", reason="field")
            value = entry.get("value")
            if not _fits(name, value):
                raise TagdocError("bad-config", reason="field")
            if entry["by"] == "person":
                self.decided[name] = value
            elif same and value is not None:
                suggested[name] = value
        if same:
            self._suggested = suggested

    # -- the fields ------------------------------------------------------------------------------
    def suggestion(self) -> dict[str, Any]:
        """tagdoc's suggestions for the document (made once): what the text says
        (:func:`tagdoc.describe.suggest`), and the program it was made with."""
        if self._suggested is None:
            found = describe.suggest(self.doc)
            tool = self.options.creator_tool or self.doc.metadata.get("creator") \
                or self.doc.metadata.get("producer")
            if tool:
                found["creatorTool"] = tool
            self._suggested = {k: v for k, v in found.items() if _fits(k, v)}
        return dict(self._suggested)

    def value(self, name: str) -> Any:
        """The value of a field: as a person decided it, else as suggested."""
        return self.decided[name] if name in self.decided else self.suggestion().get(name)

    def by(self, name: str) -> str:
        """Who decided a field: "person" or "auto"."""
        return "person" if name in self.decided else "auto"

    def set(self, name: str, value: Any) -> None:
        """A person's value for a field (None: no value, on purpose); raises "bad-field"."""
        if isinstance(value, list):
            value = [v.strip() for v in value if isinstance(v, str) and v.strip()] or None
        elif isinstance(value, str):
            value = value.strip() or None
        self.decided[name] = check(name, value)

    def restore(self, name: str) -> None:
        """Back to tagdoc's suggestion for a field."""
        self.decided.pop(name, None)

    def add_card(self, text: str) -> str:
        """Keep a copy of a card of an address book (what it may hold, medRDS 7.2), in
        place of an older copy of the same card; returns the reference to name its holder
        with (``urn:uuid:…``).  Raises "bad-card"."""
        copy = medrds.card_copy(text)
        uid = medrds.uid_of_card(copy)
        if not medrds.is_card(copy) or not uid:
            raise TagdocError("bad-card")
        cards = [c for c in (self.value("cards") or []) if medrds.uid_of_card(c) != uid]
        self.decided["cards"] = [*cards, copy]
        return medrds.reference(copy)

    def person_from_card(self, text: str) -> str:
        """The holder of a card, named as medRDS 7.2 says (the name, the first e-mail
        address, the reference to the card), its copy kept."""
        ref = self.add_card(text)
        props = medrds.properties_of(text)
        mail = next((v for n, v in props if n == "EMAIL"), None)
        identifiers = ([f"mailto:{mail}"] if mail else []) + [ref]
        return medrds.format_person(medrds.name_of_card(text) or "?", identifiers)

    def meta(self) -> dict[str, Any]:
        """The description as it will be written: every field that has a value."""
        return {name: self.value(name) for name in medrds.FIELDS
                if self.value(name) is not None}

    @property
    def signed(self) -> bool:
        """True for a PDF signed or time-stamped by someone else (it stays as it is)."""
        return self.doc.get_sigflags() > 0

    @property
    def sidecar(self) -> bool:
        """True when the description goes into a sidecar: asked for, or the PDF signed."""
        return self.options.sidecar or self.signed

    def problems(self) -> list[dict[str, str]]:
        """What is missing (a title, a kind, a date: the standard requires them) and what
        is wrong with the cards (as medRDS's own check finds it)."""
        meta = self.meta()
        missing = [{"code": "META_MISSING", "field": name, "why": f"{name} is required"}
                   for name in ("title", "kind", "date") if name not in meta]
        return missing + medrds.card_problems(meta)

    # -- the configuration document --------------------------------------------------------------
    def config(self) -> dict[str, Any]:
        """The configuration document: the input, the settings, and every field with its
        value and who decided it."""
        return {
            "format": FORMAT, "version": FORMAT_VERSION, "made_with": f"tagdoc {__version__}",
            "standard": f"https://medrds.org/spec/{medrds.standard_version()}",
            "input": {"sha256": self.sha256, "bytes": self.size,
                      "suffix": self.source.suffix.lower()},
            "options": self.options.as_dict(),
            "fields": {name: {"value": self.value(name), "by": self.by(name)}
                       for name in medrds.FIELDS},
        }

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(documents.document_bytes(self.config()))
        except OSError as e:
            raise TagdocError("unwritable") from e
        return path

    def close(self) -> None:
        self.doc.close()

    # -- the result ------------------------------------------------------------------------------
    def build(self) -> Described:
        """The result (:mod:`tagdoc.output` writes it)."""
        from tagdoc import output

        config = self.config()
        meta = self.meta()
        if self.sidecar:
            return Described(self.source, self.source.read_bytes(), medrds.serialise_xmp(meta),
                             config, self.problems())
        return Described(self.source, output.described_pdf(self.doc, meta, config), None,
                         config, self.problems())


__all__ = ["EMBEDDED", "FORMAT", "FORMAT_VERSION", "RULES", "SUFFIX", "Described", "Options",
           "Project", "check", "load_config"]
