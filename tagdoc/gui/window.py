"""The window of ``tagdoc edit``: the form, and three ways out (Apply writes the result,
Save and continue later the configuration document alone, Cancel nothing)."""

from __future__ import annotations

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tagdoc.gui.panel import DescribePanel
from tagdoc.gui.words import Words
from tagdoc.project import Project


class DescribeWindow(QMainWindow):
    """The window on one project; ``outcome`` is "applied", "saved" or "cancelled"."""

    def __init__(self, project: Project, words: Words, synchronous: bool = False) -> None:
        super().__init__()
        self.project = project
        self.w = words
        self.synchronous = synchronous
        self.outcome: str | None = None
        self.changed = False
        self.setWindowTitle(self.w("title", tool="tagdoc", name=project.source.name))
        self.resize(760, 820)
        self.panel = DescribePanel(project, words)
        self.panel.changed.connect(self._worked)
        central = QWidget()
        v = QVBoxLayout(central)
        v.addWidget(self.panel, 1)
        bar = QHBoxLayout()
        bar.addStretch(1)
        for key, action in (("cancel", self.cancel), ("later", self.later), ("apply", self.apply)):
            button = QPushButton(self.w(key))
            button.setMinimumHeight(32)
            button.clicked.connect(action)
            setattr(self, f"{key}_button", button)
            bar.addWidget(button)
        v.addLayout(bar)
        self.setCentralWidget(central)

    def _worked(self) -> None:
        self.changed = True

    def apply(self) -> None:
        self.panel.commit()
        self.outcome = "applied"
        self.close()

    def later(self) -> None:
        self.panel.commit()
        self.outcome = "saved"
        self.close()

    def cancel(self) -> None:
        self.outcome = "cancelled"
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Closing without a choice cancels; after changes, ask first."""
        if self.outcome is None:
            self.panel.commit()
            if self.changed and not self.synchronous and QMessageBox.question(
                    self, self.w("discard_title"), self.w("discard_text")) \
                    != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.outcome = "cancelled"
        event.accept()

    def self_test(self) -> None:
        """Go through the window once without a person, and apply."""
        self.apply()
