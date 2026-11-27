"""The description of a document as a form: every field of :mod:`tagdoc.medrds`, the
suggestion shown in grey until a person changes it, people and bodies taken from an
address book by their cards, and what is still missing.

The panel works on a :class:`~tagdoc.project.Project`; :meth:`DescribePanel.commit` takes
what was typed into the project (the window calls it before it closes, docrepro's window
when the person turns to another tab).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tagdoc import medrds
from tagdoc.errors import TagdocError, describe_error
from tagdoc.gui.words import Words
from tagdoc.project import CAMERA_DATE, RULES, Project

_LINES = ("creator", "institution")  # one per line
_COMMAS = ("subject", "language", "typeCode")  # comma between
_SINGLE = ("title", "date", "authenticator", "source", "creatorTool")


class DescribePanel(QWidget):
    """The form on the project :attr:`project`."""

    changed = Signal()

    def __init__(self, project: Project, words: Words, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.w = words
        self._muted = False
        outer = QVBoxLayout(self)
        help_text = QLabel(self.w("describe_help"))
        help_text.setWordWrap(True)
        outer.addWidget(help_text)
        form = QFormLayout()
        self.edits: dict[str, Any] = {}
        for name in ("title", "kind", "date", "creator", "institution", "authenticator",
                     "description", "subject", "language", "source", "typeCode",
                     "confidentiality", "creatorTool"):
            widget = self._widget(name)
            self.edits[name] = widget
            row: QWidget | QHBoxLayout = widget
            if name in ("creator", "institution", "authenticator"):
                line = QHBoxLayout()
                line.addWidget(widget, 1)
                button = QPushButton(self.w("from_card"))
                button.clicked.connect(lambda _c=False, n=name: self._card_from_file(n))
                line.addWidget(button)
                row = line
            form.addRow(self.w(f"field_{name}"), row)
            if name == "date":
                self.camera = QComboBox()
                for choice in CAMERA_DATE:
                    self.camera.addItem(self.w(f"camera_{choice}"), choice)
                self.camera.setToolTip(self.w("camera_tip"))
                self.camera.currentIndexChanged.connect(lambda _i: self._camera_chosen())
                self.camera_said = QLabel("")
                line = QHBoxLayout()
                line.addWidget(self.camera, 1)
                line.addWidget(self.camera_said)
                form.addRow(self.w("camera_date"), line)
        self.cards = QListWidget()
        self.cards.setMaximumHeight(90)
        remove = QPushButton(self.w("remove_card"))
        remove.clicked.connect(self.remove_card)
        cards = QHBoxLayout()
        cards.addWidget(self.cards, 1)
        cards.addWidget(remove)
        form.addRow(self.w("field_cards"), cards)
        outer.addLayout(form)
        restore = QPushButton(self.w("restore_all"))
        restore.clicked.connect(self.restore_all)
        outer.addWidget(restore)
        self.note = QLabel("")
        self.note.setWordWrap(True)
        outer.addWidget(self.note)
        outer.addStretch(1)
        self.show_project()

    def _widget(self, name: str) -> Any:
        """The widget of a field."""
        if name == "kind":
            box = QComboBox()
            box.addItem(self.w("kind_none"), None)
            for kind, label in medrds.kinds().items():
                box.addItem(f"{label.get(self.w.language, label['en'])} ({kind})", kind)
            box.currentIndexChanged.connect(lambda _i: self.commit())
            return box
        if name == "confidentiality":
            box = QComboBox()
            box.addItem(self.w("conf_none"), None)
            for code in medrds.CONFIDENTIALITY:
                box.addItem(self.w(f"conf_{code}"), code)
            box.currentIndexChanged.connect(lambda _i: self.commit())
            return box
        if name in (*_LINES, "description"):
            text = QPlainTextEdit()
            text.setMaximumHeight(70)
            return text
        line = QLineEdit()
        if name == "date":
            line.setToolTip(self.w("date_tip"))
        line.editingFinished.connect(self.commit)
        return line

    # -- between the form and the project --------------------------------------------------------
    @staticmethod
    def _as_text(name: str, value: Any) -> str:
        if value is None:
            return ""
        if name in _LINES:
            return "\n".join(value)
        if name in _COMMAS:
            return ", ".join(value)
        return str(value)

    def _from_widget(self, name: str) -> Any:
        widget = self.edits[name]
        if isinstance(widget, QComboBox):
            return widget.currentData()
        text = widget.toPlainText() if isinstance(widget, QPlainTextEdit) else widget.text()
        if name in _LINES:
            return [line.strip() for line in text.splitlines() if line.strip()] or None
        if name in _COMMAS:
            return [part.strip() for part in text.split(",") if part.strip()] or None
        return text.strip() or None

    def show_project(self) -> None:
        """Fill the form from the project: a person's values in black, suggestions grey."""
        self._muted = True
        try:
            for name, widget in self.edits.items():
                value = self.project.value(name)
                if isinstance(widget, QComboBox):
                    widget.setCurrentIndex(max(0, widget.findData(value)))
                elif isinstance(widget, QPlainTextEdit):
                    widget.setPlainText(self._as_text(name, value))
                else:
                    widget.setText(self._as_text(name, value))
                widget.setStyleSheet("" if self.project.by(name) == "person" else "color: grey;")
            chosen = self.camera.findData(self.project.options.camera_date)
            self.camera.setCurrentIndex(max(0, chosen))
            self.camera_said.setText(self.project.camera_moment() or self.w("camera_none"))
            self.cards.clear()
            for card in self.project.value("cards") or []:
                self.cards.addItem(medrds.name_of_card(card) or medrds.uid_of_card(card) or "?")
        finally:
            self._muted = False
        self._note()

    def _camera_chosen(self) -> None:
        """The person chose when the camera's date counts: tagdoc's suggestions anew."""
        if self._muted:
            return
        choice = self.camera.currentData()
        if choice == self.project.options.camera_date:
            return
        self.commit()
        self.project.set_camera_date(choice)
        self.changed.emit()
        self.show_project()

    def commit(self) -> None:
        """Take what the form says into the project, field by field where it differs; a
        value that does not fit is named in the note and not taken."""
        if self._muted:
            return
        wrong = []
        for name in self.edits:
            value = self._from_widget(name)
            if value == self.project.value(name):
                continue
            try:
                self.project.set(name, value)
            except TagdocError:
                wrong.append(self.w("wrong_value", field=self.w(f"field_{name}"), rule=RULES[name]))
                continue
            self.changed.emit()
        self.show_project()
        if wrong:
            self.note.setText("\n".join(wrong))

    def _note(self) -> None:
        """What is missing, and what is wrong with the cards."""
        lines = [self.w("sidecar_note")] if self.project.signed else []
        if not self.project.places:
            lines.append(self.w("no_place_note"))
        problems = self.project.problems()
        missing = [self.w(f"field_{p['field']}") for p in problems if p["code"] == "META_MISSING"]
        lines.append(self.w("missing", fields=", ".join(missing)) if missing
                     else self.w("complete"))
        lines += [self.w("card_problem", why=p["why"]) for p in problems
                  if p["code"] != "META_MISSING"]
        self.note.setText("\n".join(lines))

    # -- cards -----------------------------------------------------------------------------------
    def add_card(self, name: str, text: str) -> None:
        """Name the holder of a card in a field (authors, institution, responsible), the
        copy of the card kept with the file."""
        self.commit()
        try:
            person = self.project.person_from_card(text)
        except TagdocError as e:
            self.note.setText(describe_error(e, self.w.language))
            return
        if name in _LINES:
            self.project.set(name, [*(self.project.value(name) or []), person])
        else:
            self.project.set(name, person)
        self.changed.emit()
        self.show_project()

    def _card_from_file(self, name: str, choose: Callable[..., Any] | None = None) -> None:
        """Ask for a card file (``.vcf``) and name its holder in the field."""
        path, _filter = (choose or QFileDialog.getOpenFileName)(self, self.w("from_card"), "",
                                                                 "vCard (*.vcf)")
        if path:
            self.add_card(name, Path(path).read_text(encoding="utf-8", errors="replace"))

    def remove_card(self) -> None:
        """Remove the card selected (whoever is named with it keeps their name)."""
        row = self.cards.currentRow()
        cards = list(self.project.value("cards") or [])
        if 0 <= row < len(cards):
            del cards[row]
            self.project.set("cards", cards or None)
            self.changed.emit()
            self.show_project()

    def restore_all(self) -> None:
        """Every field back to tagdoc's suggestion."""
        for name in list(self.project.decided):
            self.project.restore(name)
        self.changed.emit()
        self.show_project()
