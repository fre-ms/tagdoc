"""The command line: about, run with a person's values and a card, failures by kind
without paths, and the window's self-test giving what run gives."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tagdoc import __version__
from tagdoc.cli import main

PATIENT = "Mustermann,Erika_1964-08-12_K7Q4MX"


def _answer(capsys: pytest.CaptureFixture[str], argv: list[str]) -> tuple[int, dict]:
    status = main(argv)
    return status, json.loads(capsys.readouterr().out)


def test_about(capsys: pytest.CaptureFixture[str]) -> None:
    status, answer = _answer(capsys, ["about"])
    assert status == 0 and answer["made_with"] == f"tagdoc {__version__}"
    assert "lab" in answer["kinds"] and "cards" in answer["fields"]


def test_run_with_values_and_a_card(tmp_path: Path, report: Path, card: Path,
                                    capsys: pytest.CaptureFixture[str]) -> None:
    status, answer = _answer(capsys, [
        "run", str(report), "--out", str(tmp_path / "out"), "--kind", "lab",
        "--institution-card", str(card), "--keyword", "Kalium", "--content-language", "de",
        "--confidentiality", "N"])
    assert status == 0, answer
    assert answer["problems"] == [] and answer["sidecar"] is None
    assert answer["decided"] == ["cards", "confidentiality", "institution", "kind", "language",
                                 "subject"]
    config = json.loads(Path(answer["config"]).read_text())
    assert config["fields"]["institution"]["value"][0].startswith(
        "Labor Muster GmbH <mailto:befunde@labor.example> <urn:uuid:")


def test_failures_without_paths(tmp_path: Path, report: Path,
                                capsys: pytest.CaptureFixture[str]) -> None:
    folder = tmp_path / PATIENT
    folder.mkdir()
    good = folder / f"{PATIENT}.pdf"
    good.write_bytes(report.read_bytes())
    cases = {"bad-field": ["run", str(good), "--date", "gestern"],
             "missing": ["run", str(good), "--creator-card", str(folder / "fehlt.vcf")],
             "usage": ["run", str(good), "--config", str(folder / "x.json"), "--kind", "lab"],
             "not-pdf": ["run", str(folder / f"{PATIENT}.jpg")]}
    (folder / f"{PATIENT}.jpg").write_bytes(b"\xff\xd8")
    for kind, argv in cases.items():
        status, answer = _answer(capsys, argv)
        assert status == 2 and answer["error"] == kind, (kind, answer)
        assert PATIENT not in json.dumps(answer, ensure_ascii=False)


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="needs PySide6")
def test_edit_self_test_gives_what_run_gives(tmp_path: Path, report: Path) -> None:
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}

    def run(argv: list[str]) -> dict:
        done = subprocess.run([sys.executable, "-m", "tagdoc", *argv], capture_output=True,
                              text=True, check=False, env=env)
        assert done.returncode == 0, done.stdout
        return dict(json.loads(done.stdout))

    edited = run(["edit", str(report), "--out", str(tmp_path / "e"), "--self-test",
                  "--language", "de"])
    ran = run(["run", str(report), "--out", str(tmp_path / "r")])
    for key in ("document", "config"):
        assert Path(edited[key]).read_bytes() == Path(ran[key]).read_bytes(), key
