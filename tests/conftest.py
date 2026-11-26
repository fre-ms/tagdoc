"""Shared fixtures: invented documents, a card of an invented address book, and the
reference library of medRDS where it is at hand (``MEDRDS``, else ``../medRDS``)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pymupdf
import pytest

MEDRDS = Path(os.environ.get("MEDRDS", Path(__file__).resolve().parents[2] / "medRDS"))
CARD = ("BEGIN:VCARD\r\nVERSION:4.0\r\nUID:urn:uuid:4D2C9B1E-7A3F-4C5D-9E8F-0A1B2C3D4E5F\r\n"
        "KIND:org\r\nFN:Labor Muster GmbH\r\nORG:Labor Muster GmbH\r\n"
        "EMAIL:befunde@labor.example\r\nTEL:+49-821-000000\r\n"
        "PHOTO:data:image/png;base64,iVBORw0KGgo=\r\nX-MEDDAV-BSNR:999999900\r\n"
        "X-SECDAV-SEALED:geheim\r\nEND:VCARD\r\n")
LINES = [("Labor am Beispielpark · Musterweg 1 · 12345 Musterstadt", 9),
         ("Laborbefund", 15),
         ("Befunddatum: 12.03.2026", 10),
         ("Patientin: Erika Mustermann, geb. 12.08.1964", 10),
         ("Kalium 5,8 mmol/l Referenzbereich 3,5 - 5,1 H", 10),
         ("Die Werte sind mit der Vorbefundung zu vergleichen und bei uns", 10),
         ("nachzufragen, wenn die Kontrolle nicht in der Praxis erfolgt.", 10)]


def make_pdf(path: Path, lines: list[tuple[str, int]] = LINES) -> Path:
    """An invented one-page report as a PDF with a text layer."""
    doc = pymupdf.open()
    page = doc.new_page()
    for n, (text, size) in enumerate(lines):
        page.insert_text((56, 80 + 22 * n), text, fontsize=size)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def report(tmp_path: Path) -> Path:
    return make_pdf(tmp_path / "befund.pdf")


@pytest.fixture
def card(tmp_path: Path) -> Path:
    path = tmp_path / "labor.vcf"
    path.write_text(CARD, encoding="utf-8")
    return path


def medrds_reads(path: Path, ext: str = "pdf") -> dict[str, Any]:
    """The metadata of a file as the reference library of medRDS reads them."""
    script = (
        "import { readFileSync } from 'node:fs';"
        f"import {{ readMetadata }} from '{MEDRDS / 'lib' / 'index.mjs'}';"
        f"const schema = JSON.parse(readFileSync('{MEDRDS / 'schema' / 'medrds.json'}', 'utf8'));"
        f"const meta = await readMetadata(readFileSync('{path}'), '{ext}', schema);"
        "console.log(JSON.stringify(meta));")
    run = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True,
                         text=True, check=True)
    return dict(json.loads(run.stdout))


needs_medrds = pytest.mark.skipif(shutil.which("node") is None or not (MEDRDS / "lib").is_dir(),
                                  reason="needs Node and the reference library of medRDS")
