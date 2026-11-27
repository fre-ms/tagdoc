"""The form: suggestions shown, a person's change taken, a card naming a body, back to
the suggestions; the words in both languages."""

from __future__ import annotations

import ast
import string
from pathlib import Path

import pytest

from tagdoc.project import Project
from tests.conftest import CARD

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

from tagdoc.gui.panel import DescribePanel  # noqa: E402
from tagdoc.gui.words import WORDS, Words  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication(["tagdoc"])


def test_words_in_both_languages() -> None:
    for key, (english, german) in WORDS.items():
        fields = [{f for _, f, _, _ in string.Formatter().parse(t) if f} for t in (english, german)]
        assert fields[0] == fields[1], key
    used: set[str] = set()
    for path in (Path(__file__).resolve().parents[1] / "tagdoc" / "gui").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "w" and node.args
                    and isinstance(node.args[0], ast.Constant)):
                used.add(node.args[0].value)
    assert used <= set(WORDS), used - set(WORDS)


def test_the_form(app: QApplication, report: Path) -> None:
    project = Project.open(report)
    panel = DescribePanel(project, Words("de"))
    try:
        assert panel.edits["title"].text() == "Laborbefund"
        assert "grey" in panel.edits["title"].styleSheet()
        assert panel.edits["kind"].currentData() == "lab"
        panel.edits["title"].setText("Kalium erhöht")
        panel.edits["date"].setText("nicht ein Datum")
        panel.commit()
        assert project.value("title") == "Kalium erhöht" and project.by("title") == "person"
        assert project.by("date") == "auto" and "ISO 8601" in panel.note.text()
        panel.add_card("institution", CARD)
        assert project.value("institution")[0].startswith("Labor Muster GmbH <mailto:")
        assert panel.cards.count() == 1 and "Vollständig" in panel.note.text()
        panel.cards.setCurrentRow(0)
        panel.remove_card()
        assert "Karte" in panel.note.text()  # the institution still names the card: missing copy
        panel.restore_all()
        assert project.decided == {} and project.value("title") == "Laborbefund"
    finally:
        panel.close()
        project.close()


def test_the_form_on_a_picture(app: QApplication, tmp_path: Path) -> None:
    """The form is the same for a picture: what was read on it and what it says of itself
    are suggested; a type without a place for a description says that it goes beside it."""
    from tests.test_formats import drawing
    from tests.test_pictures import reading_of, saved

    photo = saved(tmp_path, "jpg")
    reading_of(photo)
    project = Project.open(photo)
    panel = DescribePanel(project, Words("de"))
    try:
        assert panel.edits["title"].text() == "Laborbefund"
        assert panel.edits["kind"].currentData() == "lab"
        assert "Begleitdatei" not in panel.note.text()
        panel.edits["title"].setText("Kalium erhöht")
        panel.commit()
        assert project.value("title") == "Kalium erhöht" and project.by("title") == "person"
    finally:
        panel.close()
        project.close()
    plain = tmp_path / "scan.bmp"
    drawing().save(plain, format="BMP")
    project = Project.open(plain)
    panel = DescribePanel(project, Words("de"))
    try:
        assert "keinen Platz" in panel.note.text() and "Begleitdatei" in panel.note.text()
    finally:
        panel.close()
        project.close()


def test_the_camera_date_in_the_form(app: QApplication, tmp_path: Path) -> None:
    from tests.test_pictures import _taken, reading_of

    photo = tmp_path / "foto.jpg"
    photo.write_bytes(_taken("jpg"))
    reading_of(photo)
    project = Project.open(photo)
    panel = DescribePanel(project, Words("de"))
    try:
        assert panel.edits["date"].text() == "2026-03-12"
        assert panel.camera.currentData() == "never"
        assert panel.camera_said.text() == "2026-03-14T08:15:00+01:00"
        panel.edits["title"].setText("Mein Titel")
        panel.camera.setCurrentIndex(panel.camera.findData("first"))
        assert project.options.camera_date == "first"
        assert panel.edits["date"].text() == "2026-03-14T08:15:00+01:00"
        assert project.by("date") == "auto" and project.value("title") == "Mein Titel"
    finally:
        panel.close()
        project.close()
