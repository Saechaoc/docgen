"""Tests for docgen.orchestrator."""

from __future__ import annotations

from pathlib import Path

import pytest

from docgen.git.diff import DiffResult
from docgen.orchestrator import Orchestrator
from docgen.prompting.builder import Section
from docgen.repo_scanner import RepoScanner


class RecordingPublisher:
    """Test double that records commit invocations."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[Path], str]] = []
        self.pr_calls: list[dict[str, object]] = []

    def commit(self, repo_path: str, files, message: str) -> None:  # pragma: no cover - simple recorder
        self.calls.append((repo_path, [Path(f) for f in files], message))

    def publish_pr(
        self,
        repo_path: str,
        files,
        *,
        branch_name: str,
        base_branch: str | None = None,
        title: str,
        body: str,
        push: bool = True,
    ) -> bool:  # pragma: no cover - simple recorder
        self.pr_calls.append(
            {
                "repo_path": repo_path,
                "files": [Path(f) for f in files],
                "branch_name": branch_name,
                "base_branch": base_branch,
                "title": title,
                "body": body,
                "push": push,
            }
        )
        return True


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


class _StubDiffAnalyzer:
    def __init__(self, sections: list[str]) -> None:
        self.sections = sections
        self.calls: list[tuple[str, str]] = []

    def compute(self, repo_path: str, diff_base: str) -> DiffResult:
        self.calls.append((repo_path, diff_base))
        return DiffResult(base=diff_base, changed_files=["requirements.txt"], sections=self.sections)


class _StubPromptBuilder:
    def build(self, *args, **kwargs):  # pragma: no cover - not used in tests
        raise NotImplementedError

    def render_sections(self, manifest, signals, sections, contexts=None):  # type: ignore[no-untyped-def]
        return {
            section: Section(
                name=section,
                title=section.replace("_", " ").title(),
                body=f"UPDATED {section}",
                metadata={},
            )
            for section in sections
        }


class _FailingPromptBuilder:
    def build(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("prompt builder exploded")

    def render_sections(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("prompt builder exploded")


def test_run_update_patches_targeted_sections(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample"
    repo_root.mkdir()
    _seed_sample_repo(repo_root)

    init_orchestrator = Orchestrator()
    init_orchestrator.run_init(str(repo_root))

    diff_analyzer = _StubDiffAnalyzer(["build_and_test"])
    publisher = RecordingPublisher()
    update_orchestrator = Orchestrator(
        scanner=RepoScanner(),
        analyzers=[],
        prompt_builder=_StubPromptBuilder(),
        publisher=publisher,
        diff_analyzer=diff_analyzer,
    )

    result = update_orchestrator.run_update(str(repo_root), "origin/main")

    assert result == repo_root.resolve() / "README.md"
    content = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "UPDATED build_and_test" in content
    assert "UPDATED features" not in content
    assert publisher.pr_calls, "Expected publish_pr to be invoked"
    pr_call = publisher.pr_calls[0]
    assert pr_call["branch_name"].startswith("docgen/readme-update")


def test_run_init_falls_back_to_stub_on_prompt_failure(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample"
    repo_root.mkdir()
    _seed_sample_repo(repo_root)

    orchestrator = Orchestrator(prompt_builder=_FailingPromptBuilder())
    readme_path = orchestrator.run_init(str(repo_root))

    content = readme_path.read_text(encoding="utf-8")
    assert "placeholder README" in content
    assert "## Table of Contents" in content


def test_run_update_uses_stub_when_builder_fails(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample"
    repo_root.mkdir()
    _seed_sample_repo(repo_root)

    Orchestrator().run_init(str(repo_root))

    diff_analyzer = _StubDiffAnalyzer(["build_and_test"])
    orchestrator = Orchestrator(
        prompt_builder=_FailingPromptBuilder(),
        analyzers=[],
        diff_analyzer=diff_analyzer,
    )

    orchestrator.run_update(str(repo_root), "origin/main")

    content = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "docgen could not populate the Build & Test section automatically." in content
