"""Tests for docgen.orchestrator."""

from __future__ import annotations

from pathlib import Path

import pytest

from docgen.orchestrator import Orchestrator


class RecordingPublisher:
    """Test double that records commit invocations."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[Path], str]] = []

    def commit(self, repo_path: str, files, message: str) -> None:  # pragma: no cover - simple recorder
        self.calls.append((repo_path, [Path(f) for f in files], message))


def _seed_sample_repo(root: Path) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "app.py").write_text("print('hello world')\n", encoding="utf-8")
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "test_app.py").write_text(
        "def test_placeholder():\n    assert True\n", encoding="utf-8"
    )
    (root / "requirements.txt").write_text("fastapi\npytest\n", encoding="utf-8")
    (root / "Dockerfile").write_text("FROM python:3.11-slim\n", encoding="utf-8")


def test_run_init_creates_readme_with_quickstart(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample"
    repo_root.mkdir()
    _seed_sample_repo(repo_root)

    orchestrator = Orchestrator()
    readme_path = orchestrator.run_init(str(repo_root))

    assert readme_path.exists()
    content = readme_path.read_text(encoding="utf-8")

    assert f"# {repo_root.name}" in content
    assert "## Table of Contents" in content
    assert "## Quick Start" in content
    assert "pip install -r requirements.txt" in content
    assert "python -m pytest" in content
    assert "docker build" in content


def test_run_init_refuses_to_overwrite_existing_readme(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample"
    repo_root.mkdir()
    _seed_sample_repo(repo_root)
    (repo_root / "README.md").write_text("Existing README", encoding="utf-8")

    orchestrator = Orchestrator()

    with pytest.raises(FileExistsError):
        orchestrator.run_init(str(repo_root))


def test_run_init_respects_config_enabled_analyzers(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample"
    repo_root.mkdir()
    _seed_sample_repo(repo_root)
    (repo_root / ".docgen.yml").write_text(
        """
analyzers:
  enabled:
    - language
""",
        encoding="utf-8",
    )

    orchestrator = Orchestrator()
    readme_path = orchestrator.run_init(str(repo_root))
    content = readme_path.read_text(encoding="utf-8")

    assert "python -m pytest" not in content
    assert "Primary languages" in content


def test_run_init_commit_mode_triggers_publisher(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample"
    repo_root.mkdir()
    _seed_sample_repo(repo_root)
    (repo_root / ".docgen.yml").write_text(
        """
publish:
  mode: commit
""",
        encoding="utf-8",
    )

    publisher = RecordingPublisher()
    orchestrator = Orchestrator(publisher=publisher)
    readme_path = orchestrator.run_init(str(repo_root))

    assert publisher.calls, "Expected publisher to be invoked in commit mode"
    repo_arg, files_arg, message = publisher.calls[0]
    assert Path(repo_arg) == repo_root.resolve()
    assert Path(readme_path) in files_arg
    assert "docgen init" in message
