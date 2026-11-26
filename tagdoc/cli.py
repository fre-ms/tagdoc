"""The command line: ``tagdoc about``, ``tagdoc run`` and ``tagdoc edit`` (the window).

Every command answers with exactly one JSON object on standard output, whether it
succeeds or fails; a failure answers with its kind and its message in English and German,
and ends with exit status 2.  No answer and no message quotes a document or its path.
Values given on the command line are a person's decisions; a person or body from an
address book is given as their card (``--creator-card befunde.vcf``), named with it as
medRDS 7.2 says, and its copy kept.  The manners are doccor's (:mod:`doccor.cli`).
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from doccor import cli as frame

from tagdoc import __version__, medrds
from tagdoc.errors import TagdocError
from tagdoc.project import SUFFIX, Options, Project, load_config

INTERFACE = 1
TOOL = "tagdoc"
# the options that set a field: option name, field, whether it may be given more than once
_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ("title", "title", False), ("kind", "kind", False), ("type_code", "typeCode", True),
    ("creator", "creator", True), ("institution", "institution", True),
    ("authenticator", "authenticator", False), ("description", "description", False),
    ("keyword", "subject", True), ("content_language", "language", True),
    ("source", "source", False),
    ("creator_tool", "creatorTool", False), ("date", "date", False),
    ("confidentiality", "confidentiality", False))
_CARDS = (("creator_card", "creator", True), ("institution_card", "institution", True),
          ("authenticator_card", "authenticator", False))


def _about(args: argparse.Namespace) -> dict[str, Any]:
    """What tagdoc writes, after which standard, and whether the window can open."""
    from tagdoc import gui

    return {"version": __version__,
            "standard": f"https://medrds.org/spec/{medrds.standard_version()}",
            "fields": list(medrds.FIELDS), "kinds": medrds.kinds(), "window": gui.available()}


def _given(args: argparse.Namespace) -> bool:
    """True when the command line sets a field or a setting."""
    return any(getattr(args, name) not in (None, [], False)
               for name in [n for n, _f, _m in _FIELDS + _CARDS] + ["sidecar"])


def _read_card(path: Path) -> str:
    """The text of a card file; "missing" where there is none."""
    if not path.is_file():
        raise TagdocError("missing")
    return path.read_text(encoding="utf-8", errors="replace")


def _project(args: argparse.Namespace) -> Project:
    """The project on the PDF: from its configuration document, or fresh with the values
    given (a person's).  Both at once is a "usage"."""
    if args.config is not None:
        if _given(args):
            raise TagdocError("usage")
        return Project.open(args.file, config=load_config(args.config))
    project = Project.open(args.file, Options(sidecar=args.sidecar))
    try:
        for option, name, _many in _FIELDS:
            value = getattr(args, option)
            if value not in (None, []):
                project.set(name, value)
        for option, name, many in _CARDS:
            for path in getattr(args, option) or []:
                person = project.person_from_card(_read_card(path))
                project.set(name, [*(project.decided.get(name) or []), person] if many else person)
    except Exception:
        project.close()
        raise
    return project


def _out(args: argparse.Namespace) -> Path:
    return args.out or args.file.with_name(f"{args.file.stem}.tagdoc")


def _results(project: Project, args: argparse.Namespace) -> dict[str, Any]:
    from tagdoc import output

    described = project.build()
    paths = output.write(described, _out(args))
    return {**{k: str(v) for k, v in paths.items()},
            "sidecar": str(paths["sidecar"]) if "sidecar" in paths else None,
            "signed": project.signed, "rebased": project.rebased,
            "decided": sorted(project.decided), "problems": described.problems}


def _run(args: argparse.Namespace) -> dict[str, Any]:
    project = _project(args)
    try:
        return _results(project, args)
    finally:
        project.close()


def _edit(args: argparse.Namespace) -> dict[str, Any]:
    from tagdoc import gui

    if not gui.available():
        raise TagdocError("no-gui")
    from tagdoc.gui.app import edit

    project = _project(args)
    try:
        outcome = edit(project, language=args.language, self_test=args.self_test)
        if outcome == "cancelled":
            raise TagdocError("cancelled")
        if outcome == "saved":
            saved = project.save(_out(args) / f"{args.file.stem}{SUFFIX}")
            return {"config": str(saved), "finished": False}
        return {**_results(project, args), "finished": True}
    finally:
        project.close()


def _document_options(pr: argparse.ArgumentParser) -> None:
    pr.add_argument("file", type=Path, help="a PDF")
    pr.add_argument("--out", type=Path, help="folder for the results (default: <file>.tagdoc/)")
    pr.add_argument("--config", type=Path,
                    help="configuration to start from: <name>.tagdoc.json, or a PDF tagdoc wrote")
    pr.add_argument("--title")
    pr.add_argument("--kind", help="a kind of medRDS (see about)")
    pr.add_argument("--type-code", action="append", help="system|code, e.g. http://loinc.org|11502-2")
    pr.add_argument("--creator", action="append", help="an author: Name <mailto:…> (medRDS 7.2)")
    pr.add_argument("--institution", action="append", help="the body the authors wrote for")
    pr.add_argument("--authenticator", help="who took responsibility for the content")
    pr.add_argument("--creator-card", action="append", type=Path,
                    help="an author from an address book: their card (.vcf)")
    pr.add_argument("--institution-card", action="append", type=Path,
                    help="a body from an address book: its card (.vcf)")
    pr.add_argument("--authenticator-card", action="append", type=Path,
                    help="who took responsibility, from an address book: their card (.vcf)")
    pr.add_argument("--description")
    pr.add_argument("--keyword", action="append")
    pr.add_argument("--content-language", action="append",
                    help="the language of the content, BCP 47 (de, en-GB); repeatable")
    pr.add_argument("--source", help="where the document can be found again")
    pr.add_argument("--creator-tool", help="the program the document is made with")
    pr.add_argument("--date", help="the clinical date, ISO 8601")
    pr.add_argument("--confidentiality", choices=list(medrds.CONFIDENTIALITY))
    pr.add_argument("--sidecar", action="store_true",
                    help="write the description into a sidecar, not into the PDF")


def _parser() -> argparse.ArgumentParser:
    p = frame.Parser(prog=TOOL, description="Describe a document as medRDS says, and write it "
                                            "into the PDF or a sidecar.")
    p.add_argument("--version", action="version", version=f"{TOOL} {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("about", help="what tagdoc writes, and after which standard")
    ru = sub.add_parser("run", help="describe a PDF and write the results")
    _document_options(ru)
    ed = sub.add_parser("edit", help="open the window: check and complete the description")
    _document_options(ed)
    ed.add_argument("--language", choices=["de", "en"],
                    help="language of the window (default: the system's)")
    ed.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    return p


COMMANDS: dict[str, Callable[[argparse.Namespace], dict[str, Any]]] = {
    "about": _about, "run": _run, "edit": _edit}


def main(argv: Sequence[str] | None = None) -> int:
    return frame.main(_parser(), COMMANDS, tool=TOOL, version=__version__,
                      interface=INTERFACE, argv=argv)
