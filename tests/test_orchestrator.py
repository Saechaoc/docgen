"""Tests for docgen.orchestrator."""

from __future__ import annotations

from pathlib import Path

import pytest

from docgen.orchestrator import Orchestrator


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
