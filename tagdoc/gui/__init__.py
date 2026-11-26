"""The window of tagdoc: check and complete the description of a document (``tagdoc
edit``).  Needs PySide6 (the extra "gui").  The form is a widget of its own
(:class:`tagdoc.gui.panel.DescribePanel`), so that docrepro puts it into its window."""

from __future__ import annotations

import importlib.util


def available() -> bool:
    """True when PySide6 is installed; it is not loaded for that."""
    return importlib.util.find_spec("PySide6") is not None
