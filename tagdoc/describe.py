"""What tagdoc suggests for a document, from the text of its pages: a title, a kind, the
clinical date and the language.  Each is a suggestion for a person to confirm or change,
made by plain rules that can be followed (no model); where a rule finds nothing, the field
stays empty rather than guessed.

- **Title**: a short line in the upper part of the first page that names the document by
  the words of its kind ("Laborbefund", "Arztbrief"), else the line set in the largest type
  there (often the sender's name, so a person had better look).
- **Kind**: the first kind of the standard whose words the text holds (a laboratory report
  by "Referenzbereich", a letter by "Sehr geehrte" …); none where no words fit.
- **Clinical date**: a date the text labels so ("Datum", "Befunddatum", "vom" …), else the
  first date that is no date of birth ("geb.", "*").
- **Language**: German or English, by their commonest words.

The semantic step before tagdoc (semdoc, to come) is to make better suggestions from what
it understood; tagdoc then takes its annotations.
"""

from __future__ import annotations

import datetime
import re
from typing import Any

import pymupdf

# the kinds of medRDS by the words that tell them, in the order they are tried
_KINDS: tuple[tuple[str, str], ...] = (
    ("lab", r"\b(laborbefund|laborwerte|laborbericht|referenzbereich|normbereich|blutbild|"
            r"laboratory report|reference range)\b"),
    ("referral", r"\b(überweisungsschein|überweisung an|überweisung zur|referral form|"
                 r"referral to)\b"),
    ("prescription", r"\b(rezept|verordnung von arzneimitteln|prescription)\b"),
    ("certificate", r"\b(bescheinigung|attest|arbeitsunfähigkeitsbescheinigung|certificate)\b"),
    ("invoice", r"\b(rechnung|rechnungsbetrag|goä|invoice)\b"),
    ("consent", r"\b(einwilligung|einverständniserklärung|consent)\b"),
    ("letter", r"\b(arztbrief|entlassungsbrief|sehr geehrte|liebe kollegin|lieber kollege|"
               r"mit freundlichen|dear)\b"),
    ("report", r"\b(befund|befundbericht|entlassungsbericht|diagnosen?|report)\b"),
)
# the words a heading names a document of a kind with (a salutation tells a letter, but is
# no title)
_TITLES: dict[str, str] = {
    "lab": r"\b(laborbefund|laborbericht|laboratory report)\b",
    "referral": r"\b(überweisung|referral)\b",
    "prescription": r"\b(rezept|prescription)\b",
    "certificate": r"\b(bescheinigung|attest|certificate)\b",
    "invoice": r"\b(rechnung|invoice)\b",
    "consent": r"\b(einwilligung|einverständniserklärung|consent form)\b",
    "letter": r"\b(arztbrief|entlassungsbrief|entlassungsbericht|discharge letter)\b",
    "report": r"\b(befundbericht|befund|bericht|report)\b",
}
_MONTHS = {name: n for n, names in enumerate(
    (("januar", "january", "jan"), ("februar", "february", "feb"), ("märz", "march", "mär", "mar"),
     ("april", "apr"), ("mai", "may"), ("juni", "june", "jun"), ("juli", "july", "jul"),
     ("august", "aug"), ("september", "sept", "sep"), ("oktober", "october", "okt", "oct"),
     ("november", "nov"), ("dezember", "december", "dez", "dec")), 1) for name in names}
_DATE = re.compile(
    r"(?P<iso>\b(?P<y1>\d{4})-(?P<m1>\d{2})-(?P<d1>\d{2})\b)"
    r"|(?P<dot>\b(?P<d2>\d{1,2})\.(?P<m2>\d{1,2})\.(?P<y2>\d{4}|\d{2})\b)"
    r"|(?P<word>\b(?P<d3>\d{1,2})\.?\s+(?P<m3>[A-Za-zÄÖÜäöü]+)\.?\s+(?P<y3>\d{4})\b)")
_LABEL = re.compile(r"(datum|befunddatum|untersuchungsdatum|eingang|eingangsdatum|vom|"
                    r"date|dated)\s*:?\s*$", re.IGNORECASE)
_BIRTH = re.compile(r"(geb\.?|geboren|born|\*)\s*(am)?\s*$", re.IGNORECASE)
_GERMAN = frozenset("der die das und mit von für ist nicht bei den dem im zu wir sie".split())
_ENGLISH = frozenset("the and of with for is not to in on we you this that are".split())


def text_of(doc: pymupdf.Document) -> str:
    """The text of every page, as the PDF holds it."""
    return "\n".join(doc[n].get_text("text") for n in range(len(doc)))


def title_of(doc: pymupdf.Document, kind: str | None = None) -> str | None:
    """The title the first page suggests: in its upper part, a line of at most 60
    characters that names a document of ``kind``; else the line set in the largest type
    there (three characters at least, no more than 90); None for a page without text."""
    if len(doc) == 0:
        return None
    page = doc[0]
    words = _TITLES.get(kind) if kind else None
    best: tuple[float, float, str] | None = None
    named: tuple[float, str] | None = None
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = re.sub(r"\s+", " ", "".join(s["text"] for s in spans)).strip()
            if not 3 <= len(text) <= 90 or not re.search(r"[A-Za-zÄÖÜäöüß]{3}", text):
                continue
            top = line["bbox"][1]
            if top > page.rect.height * 0.45:
                continue
            if words and len(text) <= 60 and re.search(words, text.lower()) \
                    and (named is None or top < named[0]):
                named = (top, text)
            size = max(s["size"] for s in spans)
            larger = best is None or size > best[0] + 0.5
            if larger or (best is not None and abs(size - best[0]) <= 0.5 and top < best[1]):
                best = (size, top, text)
    if named is not None:
        return named[1]
    return best[2] if best else None


def kind_of(text: str) -> str | None:
    """The first kind whose words the text holds, or None."""
    lower = text.lower()
    for kind, words in _KINDS:
        if re.search(words, lower):
            return kind
    return None


def _date(match: re.Match[str]) -> datetime.date | None:
    """The date a match names, or None where it names none."""
    try:
        if match.group("iso"):
            return datetime.date(int(match.group("y1")), int(match.group("m1")),
                                 int(match.group("d1")))
        if match.group("dot"):
            year = int(match.group("y2"))
            if len(match.group("y2")) == 2:
                year += 2000 if year <= 69 else 1900
            return datetime.date(year, int(match.group("m2")), int(match.group("d2")))
        month = _MONTHS.get(match.group("m3").lower())
        return None if month is None else datetime.date(int(match.group("y3")), month,
                                                        int(match.group("d3")))
    except ValueError:
        return None


def date_of(text: str) -> str | None:
    """The clinical date as ISO 8601 (the date alone; its time is seldom printed): a
    labelled date, else the first that is no date of birth; None without one."""
    first: datetime.date | None = None
    for line in text.splitlines():
        for match in _DATE.finditer(line):
            found = _date(match)
            before = line[:match.start()]
            if found is None or _BIRTH.search(before):
                continue
            if _LABEL.search(before):
                return found.isoformat()
            first = first or found
    return first.isoformat() if first else None


def language_of(text: str) -> str | None:
    """"de" or "en" by their commonest words (five at least, twice as many as the other);
    None where it is not clear."""
    words = re.findall(r"[a-zäöüß]+", text.lower())
    german = sum(w in _GERMAN for w in words)
    english = sum(w in _ENGLISH for w in words)
    if german >= 5 and german >= 2 * english:
        return "de"
    if english >= 5 and english >= 2 * german:
        return "en"
    return None


def suggest(doc: pymupdf.Document) -> dict[str, Any]:
    """tagdoc's suggestions for a document: title, kind, date, language (those it found)."""
    text = text_of(doc)
    kind = kind_of(text)
    found: dict[str, Any] = {"title": title_of(doc, kind), "kind": kind, "date": date_of(text)}
    language = language_of(text)
    found["language"] = [language] if language else None
    return {k: v for k, v in found.items() if v is not None}
