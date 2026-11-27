"""The metadata of medRDS (specification, chapter 7), as far as tagdoc writes them.

medRDS is the standard a records app files documents by; its reference library (in
JavaScript) reads and writes the metadata for the apps that file.  tagdoc describes a
document before it is filed and writes the part of the metadata that says what the
document is; filing (the record, the versions, who filed it, where it came from) is the
records app's.  This module follows the reference library line by line where it writes
(``lib/xmp.mjs`` ``serialiseXmp`` and ``mergeXmp``, ``lib/pdf.mjs`` for the information
dictionary, ``lib/cards.mjs``, ``lib/people.mjs``), so that both write the same packet, and
takes the vocabulary from the standard's schema (a copy of ``schema/medrds.json``, MIT).

=====================  ===================  =======================================
key (7.1)              XMP property         tagdoc writes
=====================  ===================  =======================================
``title``              ``dc:title``         a text (``rdf:Alt``, ``x-default``)
``kind``               ``dc:type``          one of the schema's kinds (``rdf:Bag``)
``typeCode``           ``medrds:typeCode``  ``system|code`` (``rdf:Bag``)
``creator``            ``dc:creator``       people and bodies, 7.2 (``rdf:Seq``)
``institution``        ``medrds:institution``  bodies, 7.2 (``rdf:Seq``)
``authenticator``      ``medrds:authenticator``  a person, 7.2
``description``        ``dc:description``   a text (``rdf:Alt``)
``subject``            ``dc:subject``       keywords (``rdf:Bag``)
``language``           ``dc:language``      BCP 47 tags (``rdf:Bag``)
``source``             ``dc:source``        where the document can be found again
``creatorTool``        ``xmp:CreatorTool``  the program
``date``               ``xmp:CreateDate``   the clinical date, ISO 8601
``confidentiality``    ``medrds:confidentiality``  ``N``, ``R`` or ``V``
``cards``              ``medrds:cards``     copies of the cards people are named with
=====================  ===================  =======================================
"""

from __future__ import annotations

import functools
import json
import re
import xml.etree.ElementTree as ET
from importlib import resources
from typing import Any

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
XML = "http://www.w3.org/XML/1998/namespace"
NAMESPACES = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "xmp": "http://ns.adobe.com/xap/1.0/",
    "xmpMM": "http://ns.adobe.com/xap/1.0/mm/",
    "stRef": "http://ns.adobe.com/xap/1.0/sType/ResourceRef#",
    "stEvt": "http://ns.adobe.com/xap/1.0/sType/ResourceEvent#",
}
# the keys tagdoc writes (7.1), in the order the reference library writes them
FIELDS = ("title", "kind", "creator", "description", "subject", "language", "source",
          "creatorTool", "date", "typeCode", "institution", "authenticator",
          "confidentiality", "cards")
LISTS = frozenset({"creator", "subject", "language", "typeCode", "institution", "cards"})
CONFIDENTIALITY = ("N", "R", "V")


@functools.cache
def schema() -> dict[str, Any]:
    """The standard's schema, as tagdoc carries a copy of it."""
    text = resources.files("tagdoc").joinpath("schema/medrds.json").read_text(encoding="utf-8")
    return dict(json.loads(text))


def kinds() -> dict[str, dict[str, str]]:
    """The kinds of the standard (6.2) with their labels in English and German."""
    return {name: dict(kind["label"]) for name, kind in schema()["kinds"].items()}


def standard_version() -> str:
    """The version of the standard tagdoc follows, as its schema says ("0.15")."""
    return str(schema()["version"])


# -- people and bodies (7.2) ---------------------------------------------------------------------
_IDENTIFIER = re.compile(r"<([a-z][a-z0-9+.-]*:[^<>\s]+)>", re.IGNORECASE)


def parse_person(text: str) -> tuple[str, list[str]]:
    """A person or body taken apart: their name, and their identifiers (URIs)."""
    identifiers = _IDENTIFIER.findall(str(text))
    name = re.sub(r"\s+", " ", _IDENTIFIER.sub("", str(text))).strip()
    return name, identifiers


def format_person(name: str, identifiers: list[str]) -> str:
    """A person or body as the metadata write it: the name, then each identifier in angle
    brackets."""
    clean = re.sub(r"\s+", " ", re.sub(r"[<>]", "", str(name))).strip()
    return " ".join([clean, *(f"<{i}>" for i in identifiers)])


# -- cards of an address book (7.2, 7.1 ``cards``) -----------------------------------------------
CARD = "urn:uuid:"
OTHER_CARD = "urn:x-contact-uid:"
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                   re.IGNORECASE)


def _key(uid: str) -> str:
    """A UID as references are compared: a UUID without ``urn:uuid:``, in lower case."""
    bare = re.sub(r"^urn:uuid:", "", str(uid).strip(), flags=re.IGNORECASE)
    return bare.lower() if _UUID.match(bare) else bare


def normalise_card(text: str) -> str:
    """A card's text as the metadata keep it: its lines unfolded, each ended by a line feed."""
    unfolded = re.sub(r"\n[ \t]", "", re.sub(r"\r\n?", "\n", str(text)))
    lines = [line for line in unfolded.split("\n") if line.strip()]
    return "\n".join(lines) + "\n"


def card_file(text: str) -> str:
    """A card as a file of its own (``.vcf``): its lines ended by CR LF (RFC 6350)."""
    return normalise_card(text).replace("\n", "\r\n")


def properties_of(text: str) -> list[tuple[str, str]]:
    """The properties of a card: (name in upper case without its group, value)."""
    found = []
    for line in normalise_card(text).split("\n"):
        if not line:
            continue
        head, colon, value = line.partition(":")
        name = re.sub(r"^[^.]*\.", "", head.split(";")[0]).upper()
        found.append((name, value if colon else ""))
    return found


def uid_of_card(text: str) -> str | None:
    """The UID a card holds, as references are compared; None without one."""
    uid = next((value for name, value in properties_of(text) if name == "UID"), None)
    return _key(uid) if uid else None


def is_card(text: str) -> bool:
    """True when a text is a vCard: it begins and ends as one."""
    names = [name for name, _value in properties_of(text)]
    return bool(names) and names[0] == "BEGIN" and names[-1] == "END"


def reference(text: str) -> str:
    """The identifier a person or body is named with to point at a card: ``urn:uuid:`` and
    its UID, or ``urn:x-contact-uid:`` and a UID that is no UUID."""
    uid = uid_of_card(text) or ""
    return f"{CARD}{uid}" if _UUID.match(uid) else f"{OTHER_CARD}{uid}"


def card_of(person: str) -> str | None:
    """The UID of the card a person or body is named with, or None."""
    for identifier in parse_person(person)[1]:
        lower = identifier.lower()
        if lower.startswith(CARD) and _UUID.match(identifier[len(CARD):]):
            return _key(identifier)
        if lower.startswith(OTHER_CARD) and len(identifier) > len(OTHER_CARD):
            return _key(identifier[len(OTHER_CARD):])
    return None


def _foreign(name: str) -> bool:
    """True for a property that does not belong in a copy of a card (the schema's rule)."""
    rules = schema()["people"]["cards"]
    prefixed = any(name.startswith(p) for p in rules["forbiddenPrefixes"])
    return name in rules["forbidden"] or (prefixed and name not in rules["allowed"])


def card_copy(text: str) -> str:
    """The copy of a card the metadata keep: who someone is and how they are reached, and
    nothing else (no photo, no key, nothing sealed, no property of medDAV but the
    identifiers of practitioners and bodies)."""
    kept = []
    for line in normalise_card(text).split("\n"):
        if not line:
            continue
        head = line.partition(":")[0]
        name = re.sub(r"^[^.]*\.", "", head.split(";")[0]).upper()
        if not _foreign(name):
            kept.append(line)
    return "\n".join(kept) + "\n"


def name_of_card(text: str) -> str:
    """The name a card gives (``FN``, else ``ORG``), for naming its holder."""
    props = dict(properties_of(text))
    return (props.get("FN") or props.get("ORG", "").replace(";", ", ") or "").strip()


def people_in(meta: dict[str, Any]) -> list[tuple[str, str]]:
    """The people and bodies the metadata name, each with its field."""
    named = []
    for field in schema()["people"]["cards"]["fields"]:
        top, _dot, inner = field.partition(".")
        value = meta.get(top)
        if inner and isinstance(value, dict):
            value = value.get(inner)
        for text in ([] if value is None else value if isinstance(value, list) else [value]):
            named.append((field, str(text)))
    return named


def card_problems(meta: dict[str, Any]) -> list[dict[str, str]]:
    """The problems of the cards of the metadata, as the reference library finds them:
    META_INVALID, CARD_CONTENT, CARD_MISSING, CARD_UNUSED."""
    problems: list[dict[str, str]] = []
    held: set[str] = set()
    for index, card in enumerate(meta.get("cards") or []):
        uid = uid_of_card(card)
        if not is_card(card) or not uid:
            problems.append({"code": "META_INVALID", "field": "cards",
                             "why": f"copy {index + 1} of the cards is no vCard with a UID"})
            continue
        held.add(uid)
        foreign = sorted({name for name, _v in properties_of(card) if _foreign(name)})
        if foreign:
            problems.append({"code": "CARD_CONTENT", "field": "cards",
                             "why": f"the copy of card {uid} holds {', '.join(foreign)}"})
    named: set[str] = set()
    for field, text in people_in(meta):
        uid = card_of(text)
        if uid:
            named.add(uid)
            if uid not in held:
                problems.append({"code": "CARD_MISSING", "field": field,
                                 "why": f"named with card {uid}, of which there is no copy"})
    for uid in sorted(held - named):
        problems.append({"code": "CARD_UNUSED", "field": "cards",
                         "why": f"nobody is named with card {uid}"})
    return problems


# -- XMP (7.4) ----------------------------------------------------------------------------------
def _escape(value: Any) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _present(value: Any) -> bool:
    return value is not None and value != "" and not (isinstance(value, list) and not value)


def serialise_xmp(meta: dict[str, Any]) -> str:
    """The metadata as an XMP packet, as the reference library writes it (``serialiseXmp``),
    for the keys tagdoc writes."""
    own = schema()["namespace"]["prefix"]
    rows: list[str] = []

    def text(name: str, value: Any) -> None:
        if _present(value):
            rows.append(f"<{name}>{_escape(value)}</{name}>")

    def alt(name: str, value: Any) -> None:
        if _present(value):
            rows.append(f'<{name}><rdf:Alt><rdf:li xml:lang="x-default">{_escape(value)}'
                        f"</rdf:li></rdf:Alt></{name}>")

    def many(name: str, kind: str, values: Any) -> None:
        if _present(values):
            listed = values if isinstance(values, list) else [values]
            items = "".join(f"<rdf:li>{_escape(v)}</rdf:li>" for v in listed)
            rows.append(f"<{name}><rdf:{kind}>{items}</rdf:{kind}></{name}>")

    alt("dc:title", meta.get("title"))
    many("dc:type", "Bag", meta.get("kind"))
    many("dc:creator", "Seq", meta.get("creator"))
    alt("dc:description", meta.get("description"))
    many("dc:subject", "Bag", meta.get("subject"))
    many("dc:language", "Bag", meta.get("language"))
    text("dc:source", meta.get("source"))
    text("xmp:CreatorTool", meta.get("creatorTool"))
    text("xmp:CreateDate", meta.get("date"))
    many(f"{own}:typeCode", "Bag", meta.get("typeCode"))
    many(f"{own}:institution", "Seq", meta.get("institution"))
    text(f"{own}:authenticator", meta.get("authenticator"))
    text(f"{own}:confidentiality", meta.get("confidentiality"))
    many(f"{own}:cards", "Bag", [normalise_card(c) for c in meta.get("cards") or []])
    declared = [*NAMESPACES.items(), (own, schema()["namespace"]["uri"])]
    head = [
        '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>',  # the BOM, as XMP asks
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">',
        f' <rdf:RDF xmlns:rdf="{RDF}">',
        '  <rdf:Description rdf:about=""',
        *(f'    xmlns:{prefix}="{uri}"' + (">" if i == len(declared) - 1 else "")
          for i, (prefix, uri) in enumerate(declared)),
    ]
    tail = ["  </rdf:Description>", " </rdf:RDF>", "</x:xmpmeta>", '<?xpacket end="w"?>', ""]
    return "\n".join([*head, *(f"   {r}" for r in rows), *tail])


_STANDARD = {
    NAMESPACES["dc"]: {"title", "type", "creator", "description", "subject", "language", "source"},
    NAMESPACES["dcterms"]: {"conformsTo"},
    NAMESPACES["xmp"]: {"CreatorTool", "CreateDate", "MetadataDate"},
    NAMESPACES["xmpMM"]: {"DocumentID", "InstanceID", "DerivedFrom", "History"},
}


def _is_standard(tag: str) -> bool:
    """True for a property the standard writes: ``{namespace}local``; the standard's own
    namespace as a whole."""
    uri, _brace, local = tag[1:].partition("}")
    return uri == schema()["namespace"]["uri"] or local in _STANDARD.get(uri, set())


def merge_xmp(existing: str | None, meta: dict[str, Any]) -> str:
    """The metadata as a packet that keeps what an existing packet says beyond the
    standard (a PDF's mark of PDF/A, a camera's data); what the standard defines is
    replaced, as the reference library does it (``mergeXmp``)."""
    packet = serialise_xmp(meta)
    if not existing:
        return packet
    try:
        start = existing.index("<x:xmpmeta") if "<x:xmpmeta" in existing else existing.index("<")
        end = existing.rindex(">", 0, existing.rindex("<?xpacket end")) + 1 \
            if "<?xpacket end" in existing else len(existing)
        tree = ET.fromstring(existing[start:end])
    except (ValueError, ET.ParseError):
        return packet
    kept: list[ET.Element] = []
    for description in tree.iter(f"{{{RDF}}}Description"):
        for child in list(description):
            if not _is_standard(child.tag):
                kept.append(child)
        for attribute, value in description.attrib.items():
            if attribute.startswith("{") and not attribute.startswith(f"{{{RDF}}}") \
                    and not _is_standard(attribute):
                element = ET.Element(attribute)
                element.text = value
                kept.append(element)
    if not kept:
        return packet
    for prefix, uri in [*NAMESPACES.items(), ("rdf", RDF),
                        (schema()["namespace"]["prefix"], schema()["namespace"]["uri"])]:
        ET.register_namespace(prefix, uri)
    inner = "".join("   " + ET.tostring(child, encoding="unicode").strip() + "\n" for child in kept)
    foreign = f'  <rdf:Description rdf:about="">\n{inner}  </rdf:Description>'
    close = "  </rdf:Description>\n </rdf:RDF>"
    return packet.replace(close, f"  </rdf:Description>\n{foreign}\n </rdf:RDF>")


# what a packet's properties are read as: the key, how the value is held, the property
_READ: tuple[tuple[str, str, str, str], ...] = (
    ("title", "alt", "dc", "title"), ("kind", "first", "dc", "type"),
    ("creator", "list", "dc", "creator"), ("description", "alt", "dc", "description"),
    ("subject", "list", "dc", "subject"), ("language", "list", "dc", "language"),
    ("source", "text", "dc", "source"), ("creatorTool", "text", "xmp", "CreatorTool"),
    ("date", "text", "xmp", "CreateDate"), ("typeCode", "list", "", "typeCode"),
    ("institution", "list", "", "institution"), ("authenticator", "text", "", "authenticator"),
    ("confidentiality", "text", "", "confidentiality"), ("cards", "list", "", "cards"),
)


def parse_xmp(packet: str | None) -> tuple[dict[str, Any], bool]:
    """What a packet says, by the keys tagdoc writes, and whether it is a description as
    the standard writes one (it names the standard's own namespace, or says that it
    conforms to the standard).  A packet that cannot be read says nothing.

    A camera's packet names a moment and a program too (``xmp:CreateDate``,
    ``xmp:CreatorTool``): whether its date is the clinical date of a document is for the
    caller to decide, by the second value."""
    if not packet:
        return {}, False
    try:
        start = packet.index("<x:xmpmeta") if "<x:xmpmeta" in packet else packet.index("<rdf:RDF")
        close = "</x:xmpmeta>" if "<x:xmpmeta" in packet else "</rdf:RDF>"
        tree = ET.fromstring(packet[start:packet.index(close, start) + len(close)])
    except (ValueError, ET.ParseError):
        return {}, False
    own = schema()["namespace"]["uri"]
    found: dict[str, Any] = {}
    standard = own in packet

    def items(element: ET.Element) -> list[str]:
        listed = [li.text.strip() for li in element.iter(f"{{{RDF}}}li")
                  if li.text and li.text.strip()]
        return listed or ([element.text.strip()] if element.text and element.text.strip() else [])

    def default(element: ET.Element) -> str | None:
        entries = list(element.iter(f"{{{RDF}}}li"))
        for li in entries:
            if li.get(f"{{{XML}}}lang") == "x-default" and li.text and li.text.strip():
                return li.text.strip()
        return next(iter(items(element)), None)

    for description in tree.iter(f"{{{RDF}}}Description"):
        for key, form, prefix, local in _READ:
            if key in found:
                continue
            name = f"{{{NAMESPACES[prefix] if prefix else own}}}{local}"
            element = description.find(name)
            value: Any = None
            if element is not None:
                value = (default(element) if form == "alt" else items(element) if form == "list"
                         else next(iter(items(element)), None))
            elif description.get(name, "").strip():  # written as an attribute
                value = description.get(name, "").strip()
                value = [value] if form == "list" else value
            if value:
                found[key] = value
        conforms = description.find(f"{{{NAMESPACES['dcterms']}}}conformsTo")
        said = (conforms.text if conforms is not None else None) \
            or description.get(f"{{{NAMESPACES['dcterms']}}}conformsTo") or ""
        standard = standard or "medrds" in said.lower()
    return found, standard


# -- the information dictionary of a PDF (7.4) --------------------------------------------------
def pdf_date(date: str) -> str | None:
    """A date of the metadata as a PDF date: ``D:20260314081500+01'00'``."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?"
                     r"(Z|[+-]\d{2}:\d{2}))?", str(date))
    if not m:
        return None
    if m.group(4) is None:
        return f"D:{m.group(1)}{m.group(2)}{m.group(3)}"
    zone = "Z" if m.group(7) == "Z" else f"{m.group(7)[:3]}'{m.group(7)[4:]}'"
    return (f"D:{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}{m.group(5)}"
            f"{m.group(6) or '00'}{zone}")


def info_of(meta: dict[str, Any]) -> dict[str, str]:
    """The entries of a PDF's information dictionary in step with the metadata, as
    PyMuPDF names them: title, author (the names of the authors), subject (the
    description), creator (the program), creation date (the clinical date)."""
    info: dict[str, str] = {}
    if meta.get("title"):
        info["title"] = str(meta["title"])
    if meta.get("creator"):
        info["author"] = "; ".join(parse_person(c)[0] or c for c in meta["creator"])
    if meta.get("description"):
        info["subject"] = str(meta["description"])
    if meta.get("creatorTool"):
        info["creator"] = str(meta["creatorTool"])
    if meta.get("date") and (created := pdf_date(meta["date"])):
        info["creationDate"] = created
    return info
