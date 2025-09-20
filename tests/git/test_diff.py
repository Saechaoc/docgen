"""Tests for the diff analyzer mapping logic."""

from __future__ import annotations

from pathlib import Path

from docgen.git.diff import DiffAnalyzer, DiffResult


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


def test_diff_analyzer_maps_source_changes(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    calls: list[tuple[list[str], Path]] = []

    def runner(args, cwd, capture_output=False):  # type: ignore[no-untyped-def]
        calls.append((list(args), Path(cwd)))
        if args[:3] == ["git", "diff", "--name-only"]:
            return "src/app.py\nREADME.md\n"
        if args[:2] == ["git", "status"]:
            return " M src/app.py\n"
        return ""

    analyzer = DiffAnalyzer(runner=runner)
    result = analyzer.compute(str(repo), "origin/main")

    assert isinstance(result, DiffResult)
    assert result.sections == ["intro", "features", "architecture"]
    assert result.changed_files == ["src/app.py"]
    assert calls[0][0] == ["git", "diff", "--name-only", "origin/main...HEAD"]
    assert calls[0][1] == repo


def test_diff_analyzer_flags_docs_changes(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    def runner(args, cwd, capture_output=False):  # type: ignore[no-untyped-def]
        if args[:3] == ["git", "diff", "--name-only"]:
            return "docs/guide.md\n"
        if args[:2] == ["git", "status"]:
            return ""
        return ""

    analyzer = DiffAnalyzer(runner=runner)
    result = analyzer.compute(str(repo), "origin/main")

    assert result.sections[:3] == ["intro", "features", "architecture"]
    assert len(result.sections) == 10
    assert "docs/guide.md" in result.changed_files
