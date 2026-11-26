"""Open the window on a project and wait until it closes (``tagdoc edit``)."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from tagdoc.gui.window import DescribeWindow
from tagdoc.gui.words import Words
from tagdoc.project import Project


def edit(project: Project, language: str | None = None, self_test: bool = False) -> str:
    """Show the window on ``project``, brought to the front, and return how it closed."""
    app = QApplication.instance() or QApplication(["tagdoc"])
    app.setApplicationName("tagdoc")
    window = DescribeWindow(project, Words(language), synchronous=self_test)
    window.show()
    window.raise_()
    window.activateWindow()
    if self_test:
        QTimer.singleShot(0, window.self_test)
    app.exec()
    return window.outcome or "cancelled"
