"""Integration tests for README validation pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from docgen.orchestrator import Orchestrator
from docgen.prompting.builder import Section
from docgen.validators import ValidationError


class _StubDiffAnalyzer:
    def __init__(self, sections: list[str]) -> None:
        self.sections = sections

    def compute(self, repo_path: str, diff_base: str):  # type: ignore[no-untyped-def]
        from docgen.git.diff import DiffResult

        return DiffResult(base=diff_base, changed_files=["requirements.txt"], sections=self.sections)


class _HallucinatingPromptBuilder:
    def build(self, *args, **kwargs):  # pragma: no cover - not used
        raise NotImplementedError

    def render_sections(self, manifest, signals, sections, contexts=None, **_kwargs):  # type: ignore[no-untyped-def]
        generated: dict[str, Section] = {}
        for section in sections:
            generated[section] = Section(
                name=section,
                title=section.replace("_", " ").title(),
                body="This project offers instant quantum teleportation across galaxies.",
                metadata={"context": [], "evidence": {"signals": [], "context_chunks": 0}},
            )
        return generated


def _seed_repo(root: Path) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "app.py").write_text("print('hello world')\n", encoding="utf-8")
    (root / "requirements.txt").write_text("fastapi\n", encoding="utf-8")


def _read_validation_report(repo_root: Path) -> dict:
    report_path = repo_root / ".docgen" / "validation.json"
    return json.loads(report_path.read_text(encoding="utf-8"))


def test_run_init_records_validation_success(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _seed_repo(repo_root)

    orchestrator = Orchestrator()
    orchestrator.run_init(str(repo_root))

    report = _read_validation_report(repo_root)

    assert report["status"] == "passed"
    assert report["issue_count"] == 0


def test_run_update_raises_on_hallucination(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _seed_repo(repo_root)

    Orchestrator().run_init(str(repo_root))

    diff_analyzer = _StubDiffAnalyzer(["features"])
    orchestrator = Orchestrator(
        prompt_builder=_HallucinatingPromptBuilder(),
        analyzers=[],
        diff_analyzer=diff_analyzer,
    )

    with pytest.raises(ValidationError):
        orchestrator.run_update(str(repo_root), "origin/main")

    report = _read_validation_report(repo_root)
    assert report["status"] == "failed"
    assert report["issue_count"] >= 1
    assert any(issue["section"] == "features" for issue in report["issues"])

    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "quantum teleportation" not in readme


def test_run_update_skip_validation_allows_override(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _seed_repo(repo_root)

    Orchestrator().run_init(str(repo_root))

    diff_analyzer = _StubDiffAnalyzer(["features"])
    orchestrator = Orchestrator(
        prompt_builder=_HallucinatingPromptBuilder(),
        analyzers=[],
        diff_analyzer=diff_analyzer,
    )

    outcome = orchestrator.run_update(str(repo_root), "origin/main", skip_validation=True)

    assert outcome is not None
    report = _read_validation_report(repo_root)
    assert report["status"] == "skipped"
    assert report["skip_reason"] == "flag"
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "quantum teleportation" in readme
