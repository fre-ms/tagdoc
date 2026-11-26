"""tagdoc's suggestions: title, kind, the clinical date (not a date of birth), language."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from tagdoc import describe
from tests.conftest import make_pdf


def test_a_laboratory_report(report: Path) -> None:
    with pymupdf.open(report) as doc:
        found = describe.suggest(doc)
    assert found == {"title": "Laborbefund", "kind": "lab", "date": "2026-03-12",
                     "language": ["de"]}


def test_a_letter_in_english_and_dates(tmp_path: Path) -> None:
    letter = make_pdf(tmp_path / "letter.pdf", [
        ("Department of Neurology", 14), ("Dear Dr Smith,", 10),
        ("we saw the patient, born 01.02.1950, on 3 March 2026 in the clinic.", 10),
        ("The findings are in the report and we will see them again in the spring.", 10),
        ("Yours sincerely, and with thanks for the referral of the patient to us.", 10)])
    with pymupdf.open(letter) as doc:
        found = describe.suggest(doc)
    assert found["kind"] == "letter" and found["language"] == ["en"]
    assert found["date"] == "2026-03-03" and found["title"] == "Department of Neurology"
    assert describe.date_of("geb. 12.08.1964\nnichts") is None
    assert describe.date_of("Eingang: 2026-01-05, Datum 31.02.2026") == "2026-01-05"
    assert describe.kind_of("Kein Wort, das passt") is None
