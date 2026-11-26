"""The description of a document: reproducible to the byte, read by medRDS's reference
library as written, a person's fields kept when the input changed, a signed PDF left as
it is with the description in a sidecar, wrong values refused."""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest

from tagdoc import output
from tagdoc.errors import TagdocError
from tagdoc.project import EMBEDDED, Options, Project, load_config
from tests.conftest import CARD, make_pdf, medrds_reads, needs_medrds


def _written(project: Project, folder: Path) -> dict[str, bytes]:
    paths = output.write(project.build(), folder)
    return {k: p.read_bytes() for k, p in paths.items()}


def test_the_same_input_and_document_the_same_files(tmp_path: Path, report: Path) -> None:
    project = Project.open(report)
    try:
        project.set("creator", ["Dr. Erika Beispiel <mailto:beispiel@praxis.example>"])
        project.set("institution", [project.person_from_card(CARD)])
        first = _written(project, tmp_path / "a")
    finally:
        project.close()
    config = json.loads(first["config"])
    assert config["format"] == "tagdoc-config" and config["standard"].endswith("/0.15")
    assert config["fields"]["title"] == {"value": "Laborbefund", "by": "auto"}
    assert config["fields"]["creator"]["by"] == "person"
    for given in (tmp_path / "a" / "befund.tagdoc.json", tmp_path / "a" / "befund.pdf"):
        again = Project.open(report, config=load_config(given))
        try:
            assert _written(again, tmp_path / given.suffix[1:]) == first
        finally:
            again.close()
    with pymupdf.open(tmp_path / "a" / "befund.pdf") as doc:
        assert doc.embfile_names() == [EMBEDDED]
        assert doc.metadata["title"] == "Laborbefund"
        assert doc.metadata["author"] == "Dr. Erika Beispiel"
        assert doc.metadata["creationDate"] == "D:20260312"
        assert "Kalium" in doc[0].get_text()  # the pages as they came


@needs_medrds
def test_medrds_reads_what_tagdoc_wrote(tmp_path: Path, report: Path) -> None:
    project = Project.open(report)
    try:
        project.set("institution", [project.person_from_card(CARD)])
        project.set("confidentiality", "R")
        paths = output.write(project.build(), tmp_path / "out")
    finally:
        project.close()
    meta = medrds_reads(paths["pdf"])
    assert meta["title"] == "Laborbefund" and meta["kind"] == "lab"
    assert meta["date"] == "2026-03-12" and meta["confidentiality"] == "R"
    assert meta["institution"][0].endswith("<urn:uuid:4d2c9b1e-7a3f-4c5d-9e8f-0a1b2c3d4e5f>")
    assert "PHOTO" not in meta["cards"][0] and "X-MEDDAV-BSNR" in meta["cards"][0]


def test_a_changed_input_keeps_what_a_person_decided(tmp_path: Path, report: Path) -> None:
    project = Project.open(report)
    try:
        project.set("title", "Kontrolle Kalium")
        config = project.config()
    finally:
        project.close()
    other = make_pdf(tmp_path / "anders.pdf", [("Arztbrief", 15), ("Datum: 01.04.2026", 10)])
    again = Project.open(other, config=config)
    try:
        assert again.rebased and again.value("title") == "Kontrolle Kalium"
        assert again.value("date") == "2026-04-01" and again.value("kind") == "letter"
    finally:
        again.close()


def test_a_signed_pdf_stays_as_it_is(tmp_path: Path, report: Path) -> None:
    signed = tmp_path / "signiert.pdf"
    with pymupdf.open(report) as doc:
        doc.xref_set_key(doc.pdf_catalog(), "AcroForm", "<< /Fields [] /SigFlags 3 >>")
        doc.save(signed)
    project = Project.open(signed)
    try:
        assert project.signed and project.sidecar
        paths = output.write(project.build(), tmp_path / "out")
    finally:
        project.close()
    assert paths["pdf"].read_bytes() == signed.read_bytes()
    assert paths["sidecar"].name == "signiert.pdf.xmp"
    assert "<rdf:li xml:lang=\"x-default\">Laborbefund</rdf:li>" in paths["sidecar"].read_text()
    plain = Project.open(report, Options(sidecar=True))
    try:
        assert plain.sidecar and plain.build().sidecar is not None
    finally:
        plain.close()


def test_wrong_values_and_what_is_missing(tmp_path: Path) -> None:
    empty = make_pdf(tmp_path / "leer.pdf", [("123", 10)])
    project = Project.open(empty)
    try:
        assert {p["field"] for p in project.problems()} == {"title", "kind", "date"}
        for name, value in (("kind", "brief"), ("date", "12.03.2026"), ("confidentiality", "X"),
                            ("language", ["deutsch!"]), ("typeCode", ["11502-2"])):
            with pytest.raises(TagdocError) as caught:
                project.set(name, value)
            assert caught.value.kind == "bad-field" and caught.value.details["field"] == name
        with pytest.raises(TagdocError) as caught:
            project.add_card("kein vCard")
        assert caught.value.kind == "bad-card"
    finally:
        project.close()
    with pytest.raises(TagdocError) as caught:
        Project.open(tmp_path / "foto.jpg")
    assert caught.value.kind == "missing"
    (tmp_path / "foto.jpg").write_bytes(b"\xff\xd8")
    with pytest.raises(TagdocError) as caught:
        Project.open(tmp_path / "foto.jpg")
    assert caught.value.kind == "not-pdf"
