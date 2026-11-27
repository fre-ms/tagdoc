"""A picture stays a picture: tagdoc describes it and writes the description into it where
its type has a place, else beside it; what it suggests comes from what was read on the
picture (the reading ocrdoc laid beside it) and from what the picture says of itself; the
same picture and document give the same files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tagdoc import exif, formats, medrds, output
from tagdoc.cli import main
from tagdoc.project import Options, Project, load_config
from tests.test_formats import SAVE, drawing, picture, pixels

LINES = (("Labor am Beispielpark", 40, 22), ("Laborbefund", 90, 38),
         ("Befunddatum: 12.03.2026", 150, 24),
         ("Patientin: Erika Mustermann, geb. 12.08.1964", 190, 24),
         ("Kalium 5,8 mmol/l Referenzbereich 3,5 - 5,1 H", 230, 24),
         ("Die Werte sind mit der Vorbefundung zu vergleichen und bei uns", 270, 24),
         ("nachzufragen, wenn die Kontrolle nicht in der Praxis erfolgt ist.", 310, 24))


def reading_of(path: Path) -> Path:
    """What ocrdoc would lay beside a picture: a reading of the invented report, naming
    the picture by its SHA-256, the boxes in the picture's pixels."""
    text, words = "", []
    for line, top, height in LINES:
        x = 60.0
        for word in line.split(" "):
            words.append({"text": word, "start": len(text), "end": len(text) + len(word),
                          "box": [x, top, x + 11.0 * len(word), top + height]})
            text += word + " "
            x += 11.0 * len(word) + 9
        text = text[:-1] + "\n"
    reading = {"format": "ocrdoc-reading", "version": 2, "made_with": "ocrdoc 0.4.0",
               "reader": "rapidocr",
               "input": {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
               "pages": [{"page": 1, "unit": "px", "width": 1240, "height": 1755,
                          "source": "ocr", "text": text[:-1], "markdown": "", "words": words,
                          "regions": [], "tables": []}]}
    beside = path.with_name(f"{path.stem}.reading.json")
    beside.write_text(json.dumps(reading, ensure_ascii=False), encoding="utf-8")
    return beside


def saved(folder: Path, ending: str, **options: object) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"foto.{ending}"
    path.write_bytes(picture(ending, **options))  # type: ignore[arg-type]
    return path


def written(project: Project, folder: Path) -> dict[str, bytes]:
    paths = output.write(project.build(), folder)
    return {k: p.read_bytes() for k, p in paths.items()}


@pytest.mark.parametrize("ending", list(SAVE))
def test_a_picture_is_described_and_stays_a_picture(tmp_path: Path, ending: str) -> None:
    """The description goes into the picture, which comes back under its own name with
    the same pixels; the configuration document lies beside it; from both, the same
    files again."""
    source = saved(tmp_path / "in", ending)
    reading_of(source)
    project = Project.open(source)
    try:
        assert project.picture and not project.sidecar
        project.set("creator", ["Dr. Erika Müller <mailto:mueller@labor.example>"])
        project.set("description", "Kontrolle des Kaliums")
        described = project.build()
        paths = output.write(described, tmp_path / "out")
    finally:
        project.close()
    assert described.written == formats.places(f".{ending}") and described.why_sidecar is None
    assert {p.name for p in (tmp_path / "out").iterdir()} == {f"foto.{ending}",
                                                               "foto.tagdoc.json"}
    out = paths["document"].read_bytes()
    assert pixels(out) == pixels(source.read_bytes())
    held = formats.held(out, f".{ending}")
    said, standard = medrds.parse_xmp(held.packet)
    assert standard and said["title"] == "Laborbefund" and said["kind"] == "lab"
    assert said["date"] == "2026-03-12" and said["language"] == ["de"]
    assert said["description"] == "Kontrolle des Kaliums"
    # the camera the picture names (a GIF has no EXIF to name one)
    assert said.get("creatorTool") == (None if ending == "gif" else "Beispielfon 7 (Kamera 3.1)")
    if ending != "gif":  # in step with the description
        assert held.texts[exif.DESCRIPTION] == "Kontrolle des Kaliums"
        assert held.texts[exif.ARTIST] == "Dr. Erika Müller"
        assert held.texts[exif.MAKE] == "Beispielfon"
    config = load_config(paths["config"])
    assert config["input"]["suffix"] == f".{ending}"
    assert config["fields"]["title"] == {"value": "Laborbefund", "by": "auto"}
    assert config["fields"]["description"]["by"] == "person"
    again = Project.open(source, config=config)
    try:
        assert written(again, tmp_path / "again") == {k: p.read_bytes() for k, p in paths.items()}
    finally:
        again.close()


@pytest.mark.parametrize(("ending", "magic"), (("bmp", b"BM"), ("pnm", b"P6")))
def test_a_picture_without_a_place_stays_as_it_came(tmp_path: Path, ending: str,
                                                    magic: bytes) -> None:
    """A BMP and a PNM have no place for a description: the picture is handed on byte for
    byte, and the description lies beside it, in a sidecar named after the file."""
    import io

    buffer = io.BytesIO()
    drawing().save(buffer, format="BMP" if ending == "bmp" else "PPM")  # type: ignore[attr-defined]
    source = tmp_path / f"scan.{ending}"
    source.write_bytes(buffer.getvalue())
    assert source.read_bytes().startswith(magic)
    project = Project.open(source)
    try:
        assert project.sidecar and project.places == ()
        project.set("title", "Befund")
        described = project.build()
        paths = output.write(described, tmp_path / "out")
    finally:
        project.close()
    assert (described.written, described.why_sidecar) == (("sidecar",), "no-place")
    assert paths["document"].read_bytes() == source.read_bytes()
    assert paths["sidecar"].name == f"scan.{ending}.xmp"
    assert medrds.parse_xmp(paths["sidecar"].read_text(encoding="utf-8"))[0]["title"] == "Befund"


def test_a_sidecar_where_it_is_asked_for_or_the_file_cannot_take_it(tmp_path: Path) -> None:
    """Asked for, the picture stays as it came; so it does where the description does not
    fit into it (a JPEG takes a packet of 64 kilobytes at most): the answer says why."""
    source = saved(tmp_path, "jpg")
    for options, change, why in ((Options(sidecar=True), "Kurz", "asked"),
                                 (Options(), "lang " * 14000, "xmp-too-long")):
        project = Project.open(source, options)
        try:
            project.set("title", "Befund")
            project.set("description", change)
            described = project.build()
        finally:
            project.close()
        assert (described.written, described.why_sidecar) == (("sidecar",), why)
        assert described.document == source.read_bytes() and described.sidecar is not None
        assert "<dc:title>" in described.sidecar


def test_what_tagdoc_suggests_for_a_picture(tmp_path: Path) -> None:
    """From what was read on it: the title, the kind, the clinical date, the language,
    by the rules that hold for the text of a PDF.  From what it says of itself: a
    description, who made it, the camera.  A reading of another picture counts for
    nothing; a camera's date is not the clinical date."""
    source = saved(tmp_path / "a", "jpg")
    beside = reading_of(source)
    project = Project.open(source)
    try:
        assert project.suggestion() == {
            "title": "Laborbefund", "kind": "lab", "date": "2026-03-12", "language": ["de"],
            "description": "ALTE BESCHREIBUNG DER KAMERA",
            "creatorTool": "Beispielfon 7 (Kamera 3.1)"}
    finally:
        project.close()
    other = saved(tmp_path / "b", "jpg", quality=40)  # another picture, the same name
    (tmp_path / "b" / beside.name).write_bytes(beside.read_bytes())
    project = Project.open(other)
    try:
        assert "title" not in project.suggestion() and "date" not in project.suggestion()
    finally:
        project.close()
    camera = ('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="' + medrds.RDF + '">'
              '<rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/"'
              ' xmlns:dc="http://purl.org/dc/elements/1.1/" xmp:CreateDate="2026-03-14T08:15:00"'
              ' xmp:CreatorTool="Scan-App 2"><dc:creator><rdf:Seq><rdf:li>Wer es aufnahm</rdf:li>'
              "</rdf:Seq></dc:creator></rdf:Description></rdf:RDF></x:xmpmeta>")
    taken = tmp_path / "c" / "foto.png"
    taken.parent.mkdir()
    taken.write_bytes(formats.written(picture("png", False), ".png", camera, {})[0])
    project = Project.open(taken)
    try:
        assert project.suggestion() == {"creator": ["Wer es aufnahm"], "creatorTool": "Scan-App 2"}
    finally:
        project.close()


def test_a_description_the_picture_carries_already(tmp_path: Path) -> None:
    """A picture described before says what it is: every field of that description is
    suggested again, before any rule; the program docrepro names for it still counts."""
    source = saved(tmp_path / "in", "png", with_exif=False)
    first = Project.open(source)
    try:
        for name, value in (("title", "Entlassbrief"), ("kind", "letter"), ("date", "2026-02-01"),
                            ("subject", ["Kardiologie"]), ("confidentiality", "R")):
            first.set(name, value)
        once = output.write(first.build(), tmp_path / "once")["document"]
    finally:
        first.close()
    reading_of(once)  # a text that would suggest another title, kind and date
    second = Project.open(once, Options(creator_tool="docrepro 0.8.0"))
    try:
        assert second.suggestion() == {
            "title": "Entlassbrief", "kind": "letter", "date": "2026-02-01", "language": ["de"],
            "subject": ["Kardiologie"], "confidentiality": "R", "creatorTool": "docrepro 0.8.0"}
        assert second.decided == {} and second.problems() == []
    finally:
        second.close()


def test_a_changed_picture_keeps_what_a_person_decided(tmp_path: Path) -> None:
    """The step before made the picture anew: a person's fields stay, tagdoc's own are
    suggested again."""
    source = saved(tmp_path / "a", "jpg")
    project = Project.open(source)
    try:
        project.set("title", "Mein Titel")
        config = project.config()
    finally:
        project.close()
    brighter = saved(tmp_path / "b", "jpg", quality=60)
    reading_of(brighter)
    again = Project.open(brighter, config=config)
    try:
        assert again.rebased and again.value("title") == "Mein Titel"
        assert again.by("title") == "person" and again.value("kind") == "lab"
    finally:
        again.close()


def test_a_picture_on_the_command_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = saved(tmp_path / "in", "heic")
    reading_of(source)
    assert main(["run", str(source), "--out", str(tmp_path / "out"), "--keyword", "Kalium"]) == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer["document"] == str(tmp_path / "out" / "foto.heic")
    assert answer["written"] == ["xmp", "exif"] and answer["sidecar"] is None
    assert answer["why_sidecar"] is None and answer["problems"] == [] and not answer["signed"]
    assert main(["run", str(source), "--out", str(tmp_path / "again"), "--config",
                 answer["config"]]) == 0
    again = json.loads(capsys.readouterr().out)
    for key in ("document", "config"):
        assert Path(again[key]).read_bytes() == Path(answer[key]).read_bytes(), key
    assert main(["run", str(source), "--out", str(tmp_path / "in")]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "same-as-source"
    assert main(["run", str(source), "--out", str(tmp_path / "beside"), "--sidecar"]) == 0
    beside = json.loads(capsys.readouterr().out)
    assert beside["written"] == ["sidecar"] and beside["why_sidecar"] == "asked"
    assert Path(beside["sidecar"]).name == "foto.heic.xmp"
    assert Path(beside["document"]).read_bytes() == source.read_bytes()
    assert main(["about"]) == 0
    about = json.loads(capsys.readouterr().out)
    assert about["places"]["pdf"] == ["xmp", "info"] and about["places"]["jpg"] == ["xmp", "exif"]
    assert about["places"]["gif"] == ["xmp"] and about["places"]["bmp"] == ["sidecar"]
    assert about["heic"] is True and set(about["places"]) > {"heic", "tiff", "webp", "png", "pnm"}
