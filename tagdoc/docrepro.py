"""tagdoc as step 40 of docrepro, through the entry point ``docrepro.steps`` (see
docrepro's ``steps``): it takes the document of the step before (ocrdoc's PDF with its
text, or a picture with its reading beside it) and writes the description into it, or
beside it into a sidecar.  docrepro does not import
this module's types; it calls the methods its ``Adapter`` names, and :meth:`panel` for its
window.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import tagdoc
from tagdoc.project import Options, Project


class TagdocAdapter:
    """How docrepro works tagdoc."""

    def __init__(self) -> None:
        self.version = tagdoc.__version__

    def open(self, source: Path, config: dict[str, Any] | None, settings: dict[str, Any],
             scratch: Path) -> Project:
        """tagdoc's project on the document of the step before; the program the document
        is made with is the one docrepro names (``creator_tool``)."""
        options = Options(sidecar=bool(settings.get("sidecar", False)),
                          creator_tool=settings.get("creator_tool"),
                          camera_date=str(settings.get("camera_date") or "never"))
        return Project.open(source, None if config else options, config)

    def use_originals(self, project: Project, originals: list[Path]) -> None:
        """The files the chain began with: their camera data count as well (optdoc's
        prepared page carries none)."""
        project.originals = list(originals)

    def config(self, project: Project) -> dict[str, Any]:
        return project.config()

    def write(self, project: Project, folder: Path, stem: str,
              progress: Callable[[int, int], None] | None) -> dict[str, Path]:
        from tagdoc import output

        if progress is not None:
            progress(1, 1)
        return output.write(project.build(), folder, stem)

    def dropped(self, project: Project) -> list[int]:
        return []  # a description is of the whole document: a person's fields stay

    def close(self, project: Project) -> None:
        project.close()

    def panel(self, project: Project, words: Any) -> Any:
        """The form for docrepro's window."""
        from tagdoc.gui.panel import DescribePanel

        return DescribePanel(project, words)
