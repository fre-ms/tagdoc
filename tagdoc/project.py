"""The description of one document, and its configuration document.

A project holds what tagdoc writes about a document: every field of :mod:`tagdoc.medrds`
with its value and who decided it ("auto": tagdoc's suggestion, "person"), and the copies
of the cards the people it names are named with.  Its configuration document
(``<stem>.tagdoc.json``, format ``tagdoc-config``) is that, and nothing else (no paths, no
times):

- **Reproducing.**  The input and the document give the same result, byte for byte.
- **Resuming.**  The window saves the document and opens it again where the person stopped;
  the PDF tagdoc writes carries it too (``tagdoc.json``); beside a picture it lies as a
  file, since a picture has no place for it.
- **Going on after an earlier step changed.**  A description is of the whole document, not
  of a page: when the input changed (optdoc or ocrdoc made it anew), every field a person
  decided stays, and tagdoc's own suggestions are made again from the new text
  (:attr:`Project.rebased`).

**A document need not be a PDF.**  tagdoc describes a picture as well and writes the
description into it where its format has a place (:mod:`tagdoc.formats`); the picture
stays a picture, its own data untouched.

**Where the description goes into a sidecar** (medRDS 7.5): a PDF signed or time-stamped
by someone else must stay as it is; a picture of a type without a place for a description
(BMP, PNM), or one tagdoc cannot write into without risk, stays as it came; and wherever
the person asks for one.

**What tagdoc suggests** comes from three sides, in this order: what the document says of
itself as the standard writes it (a description it carries already: every field of it);
what its text says, by rules (:mod:`tagdoc.describe`; the text of a PDF, and for a
picture the reading ocrdoc laid beside it); and what a picture says of itself otherwise
(its XMP and EXIF: a description, who made it, keywords, the camera or program).

**The camera's date** says when a photo was taken.  Whether it is the clinical date is the
person's choice (``Options.camera_date``): for a photographed laboratory report it is not
(the report is older than its photo), for the photo of a skin finding it is.  By default
it is suggested nowhere (``never``); ``missing`` suggests it where the text names no date,
``first`` before the date the text names.  It is read from the picture (its EXIF, else
its XMP), from the pictures a PDF holds on its first page (typdoc binds a photo byte for
byte), and from the files the document was made from where the caller names them
(:attr:`Project.originals`: docrepro names its original, since optdoc's prepared page
carries no camera data).
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymupdf
from doccor import documents
from doccor import pictures as view
from doccor.errors import DocError

from tagdoc import __version__, describe, exif, formats, medrds
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


CAMERA_DATE = ("never", "missing", "first")  # when the camera's date is the clinical date


@dataclass
class Options:
    """The settings: the description into a sidecar rather than into the document
    (``sidecar``), the program the document is made with (``creator_tool``; docrepro gives
    its own; else tagdoc suggests what the document names), and when the date a camera
    gives is suggested as the clinical date (``camera_date``: ``never``, ``missing``
    where the text names none, ``first`` before the text's)."""

    sidecar: bool = False
    creator_tool: str | None = None
    camera_date: str = "never"

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: Any) -> Options:
        if not isinstance(d, dict):
            raise TagdocError("bad-config", reason="field")
        options = cls()
        for name, kinds in (("sidecar", (bool,)), ("creator_tool", (str, type(None))),
                            ("camera_date", (str,))):
            if name in d:
                if not isinstance(d[name], kinds):
                    raise TagdocError("bad-config", reason="field")
                setattr(options, name, d[name])
        if options.camera_date not in CAMERA_DATE:
            raise TagdocError("bad-config", reason="field")
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
    """The result: the document as tagdoc gives it (with the description inside, or as
    it came where the description goes into a sidecar), the sidecar's packet (None without
    one), the configuration document, what is still missing or wrong, where the
    description was written ("xmp" and "info" in a PDF, "xmp" and "exif" in a picture, or
    "sidecar"), and why it went into a sidecar where it did ("asked", "signed", or why the
    document had no place for it)."""

    source: Path
    document: bytes
    sidecar: str | None
    config: dict[str, Any]
    problems: list[dict[str, str]] = field(default_factory=list)
    written: tuple[str, ...] = ()
    why_sidecar: str | None = None


def _reading(source: Path, sha256: str) -> dict[str, Any] | None:
    """ocrdoc's reading of a picture, which lies beside it (``<stem>.reading.json``),
    where it is of this very picture: a reading names the file it was made of by its
    SHA-256, and ocrdoc hands a picture on as it came."""
    try:
        reading = json.loads(source.with_name(f"{source.stem}.reading.json")
                             .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(reading, dict) or reading.get("format") != "ocrdoc-reading":
        return None
    named = reading.get("input")
    return reading if isinstance(named, dict) and named.get("sha256") == sha256 else None


_MOMENTS = (("http://ns.adobe.com/exif/1.0/", "DateTimeOriginal"),
            ("http://ns.adobe.com/photoshop/1.0/", "DateCreated"),
            ("http://ns.adobe.com/xap/1.0/", "CreateDate"))


def _xmp_taken(packet: str | None) -> str | None:
    """When a picture was taken, as a camera's XMP says (``exif:DateTimeOriginal``, else
    ``photoshop:DateCreated``, else ``xmp:CreateDate``): with its time where the offset
    from UTC is given, else the date alone."""
    if not packet:
        return None
    try:
        start = packet.index("<x:xmpmeta") if "<x:xmpmeta" in packet else packet.index("<rdf:RDF")
        close = "</x:xmpmeta>" if "<x:xmpmeta" in packet else "</rdf:RDF>"
        tree = ET.fromstring(packet[start:packet.index(close, start) + len(close)])
    except (ValueError, ET.ParseError):
        return None
    for uri, local in _MOMENTS:
        name = f"{{{uri}}}{local}"
        for description in tree.iter(f"{{{medrds.RDF}}}Description"):
            element = description.find(name)
            said = (element.text if element is not None else None) or description.get(name)
            if said and said.strip():
                return _as_date(said.strip())
    return None


def _as_date(said: str) -> str | None:
    """A moment of XMP as the metadata keep a date: as it is where it has an offset from
    UTC or no time, else the date alone."""
    if medrds.pdf_date(said) is not None:
        return said
    date = said[:10]
    return date if medrds.pdf_date(date) is not None else None


def _taken_in(data: bytes, suffix: str) -> str | None:
    """When the picture in a file was taken: as its EXIF says, else its XMP."""
    said = formats.held(data, suffix)
    return said.taken or _xmp_taken(said.packet)


def _device(texts: dict[int, str]) -> str | None:
    """The camera or program a picture's EXIF names: the maker and the model, with the
    program in brackets; else the program alone."""
    make, model = texts.get(exif.MAKE, ""), texts.get(exif.MODEL, "")
    device = model if model.lower().startswith(make.lower()) else f"{make} {model}".strip()
    program = texts.get(exif.SOFTWARE, "")
    if device and program:
        return f"{device} ({program})"
    return device or program or None


def _pictures_on(doc: pymupdf.Document) -> list[tuple[bytes, str]]:
    """The pictures on the first page of a PDF as files, where they can be had as they
    came: a JPEG that is the page's image (its stream is the file), and a file associated
    with the page (how typdoc binds a picture that is no JPEG)."""
    page = doc[0]
    found: list[tuple[bytes, str]] = []
    for image in page.get_images(full=True):
        try:
            if doc.xref_get_key(image[0], "Filter")[1] == "/DCTDecode":
                found.append((doc.xref_stream_raw(image[0]), ".jpg"))
        except Exception:  # a stream MuPDF cannot give: nothing of it
            continue
    kind, listed = doc.xref_get_key(page.xref, "AF")
    if kind == "array":
        for ref in re.findall(r"(\d+) 0 R", listed):
            try:
                name = doc.xref_get_key(int(ref), "UF")[1] or doc.xref_get_key(int(ref), "F")[1]
                kind_file, file_ref = doc.xref_get_key(int(ref), "EF/F")
                if kind_file == "xref":
                    found.append((doc.xref_stream(int(file_ref.split()[0])),
                                  Path(name.strip("()")).suffix))
            except Exception:
                continue
    return found


class Project:
    """The description of one document, a PDF or a picture; see the module."""

    def __init__(self, source: Path, doc: pymupdf.Document | None, sha256: str, size: int,
                 options: Options) -> None:
        self.source = source
        self.doc = doc  # a PDF; None for a picture
        self.picture = doc is None
        self.data = source.read_bytes() if self.picture else b""  # a picture, as it came
        self.said = (formats.held(self.data, source.suffix) if self.picture
                     else formats.Held())  # what a picture says of itself
        self.sha256 = sha256
        self.size = size
        self.options = options
        # the files the document was made from, whose camera data count as well (docrepro
        # names its original); no setting: the configuration document holds what was found
        self.originals: list[Path] = []
        self.decided: dict[str, Any] = {}  # a person's values, by field
        self._suggested: dict[str, Any] | None = None
        self.rebased = False

    @classmethod
    def open(cls, source: str | Path, options: Options | None = None,
             config: dict[str, Any] | None = None) -> Project:
        """A project on a PDF or a picture: fresh, or as ``config`` left it.  Raises
        "missing", "unsupported" (neither a PDF nor a picture), "unreadable", "encrypted",
        "bad-config"."""
        source = Path(source)
        if not source.is_file():
            raise TagdocError("missing")
        suffix = source.suffix.lower()
        doc: pymupdf.Document | None = None
        if suffix == ".pdf":
            try:
                doc = pymupdf.open(source)
            except Exception as e:  # MuPDF words its failures with the file's name
                raise TagdocError("unreadable") from e
            if doc.needs_pass:
                doc.close()
                raise TagdocError("encrypted")
        elif view.is_picture(source):
            try:
                with source.open("rb") as file:
                    head = file.read(16)
            except OSError as e:
                raise TagdocError("unreadable") from e
            if not formats.genuine(head, suffix):
                raise TagdocError("unreadable")
        else:
            raise TagdocError("unsupported", suffix=suffix or "(none)")
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
        """tagdoc's suggestions for the document (made once); see the module for where
        they come from."""
        if self._suggested is None:
            found: dict[str, Any] = {}
            if self.doc is not None:
                found = describe.suggest(self.doc)
                packet = self.doc.get_xml_metadata() or None
                tool = self.doc.metadata.get("creator") or self.doc.metadata.get("producer")
                said, standard = medrds.parse_xmp(packet)
            else:
                reading = _reading(self.source, self.sha256)
                if reading is not None:
                    found = describe.suggest_from_reading(reading)
                said, standard = medrds.parse_xmp(self.said.packet)
                texts = self.said.texts
                own = {"title": said.get("title"),
                       "description": said.get("description") or texts.get(exif.DESCRIPTION),
                       "creator": said.get("creator") or ([texts[exif.ARTIST]]
                                                          if exif.ARTIST in texts else None),
                       "subject": said.get("subject")}
                for name, value in own.items():
                    if value and name not in found:
                        found[name] = value
                tool = said.get("creatorTool") or _device(texts)
            moment = self.camera_moment() if self.options.camera_date != "never" else None
            if moment and (self.options.camera_date == "first" or "date" not in found):
                found["date"] = moment
            if standard:  # a description as the standard writes it: every field of it
                found.update({k: v for k, v in said.items() if k in medrds.FIELDS})
            tool = self.options.creator_tool or found.get("creatorTool") or tool
            if tool:
                found["creatorTool"] = tool
            self._suggested = {k: v for k, v in found.items() if _fits(k, v)}
        return dict(self._suggested)

    def camera_moment(self) -> str | None:
        """When the picture was taken, as a camera says it (see the module): the picture's
        own EXIF or XMP; for a PDF, the pictures on its first page; else the files the
        document was made from (:attr:`originals`)."""
        if self.picture:
            moment = _taken_in(self.data, self.source.suffix)
            if moment:
                return moment
        elif self.doc is not None and len(self.doc):
            for data, suffix in _pictures_on(self.doc):
                moment = _taken_in(data, suffix)
                if moment:
                    return moment
        for original in self.originals:
            try:
                moment = _taken_in(Path(original).read_bytes(), Path(original).suffix)
            except OSError:
                continue
            if moment:
                return moment
        return None

    def set_camera_date(self, choice: str) -> None:
        """When the camera's date is suggested as the clinical date (``never``, ``missing``,
        ``first``); tagdoc's suggestions are made again, a person's values stay."""
        if choice not in CAMERA_DATE:
            raise TagdocError("bad-field", field="camera_date", rule="never, missing or first")
        self.options.camera_date = choice
        self._suggested = None

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
        return self.doc is not None and self.doc.get_sigflags() > 0

    @property
    def places(self) -> tuple[str, ...]:
        """Where the document has a place for a description: "xmp" and "info" in a PDF,
        "xmp" and (but for a GIF) "exif" in a picture; nothing for a picture of a type
        without one."""
        return formats.places(self.source.suffix) if self.picture else ("xmp", "info")

    @property
    def sidecar(self) -> bool:
        """True when the description goes into a sidecar: asked for, the PDF signed, or
        a picture of a type without a place for it."""
        return self.options.sidecar or self.signed or not self.places

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
        if self.doc is not None:
            self.doc.close()

    # -- the result ------------------------------------------------------------------------------
    def build(self) -> Described:
        """The result (:mod:`tagdoc.output` writes it)."""
        from tagdoc import output

        config = self.config()
        meta = self.meta()
        why = ("asked" if self.options.sidecar else "signed" if self.signed
               else None if self.places else "no-place")
        if why is None and self.doc is not None:
            return Described(self.source, output.described_pdf(self.doc, meta, config), None,
                             config, self.problems(), ("xmp", "info"))
        if why is None:
            # in step with the description: what EXIF has a text for (medRDS 7.4)
            names = "; ".join(medrds.parse_person(c)[0] or c for c in meta.get("creator") or [])
            texts = {exif.DESCRIPTION: meta.get("description"), exif.ARTIST: names or None}
            try:
                picture, done = formats.written(self.data, self.source.suffix,
                                                medrds.merge_xmp(self.said.packet, meta), texts)
                return Described(self.source, picture, None, config, self.problems(), done)
            except formats.NoPlace as e:  # it stays as it came: the description beside it
                why = e.reason
        return Described(self.source, self.data if self.picture else self.source.read_bytes(),
                         medrds.serialise_xmp(meta), config, self.problems(), ("sidecar",), why)


__all__ = ["EMBEDDED", "FORMAT", "FORMAT_VERSION", "RULES", "SUFFIX", "Described", "Options",
           "Project", "check", "load_config"]
