"""Tests for docgen.orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from docgen.analyzers import Analyzer
from docgen.git.diff import DiffResult
from docgen.models import Signal
from docgen.orchestrator import Orchestrator, UpdateOutcome
from docgen.prompting.builder import PromptBuilder, Section
from docgen.prompting.constants import DEFAULT_SECTIONS
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
        labels=None,
        update_existing: bool = False,
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
                "labels": labels,
                "update_existing": update_existing,
            }
        )
        return True


class RecordingLLMRunner:
    """Simple runner that captures prompts for assertions."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, prompt: str, *, system: str | None = None, max_tokens: int | None = None) -> str:
        self.calls.append({
            "prompt": prompt,
            "system": system,
            "max_tokens": max_tokens,
        })
        section_title = ""
        for line in prompt.splitlines():
            if line.startswith("Section: "):
                section_title = line.split("Section: ", 1)[1]
                break
        if not section_title:
            section_title = f"Section {len(self.calls)}"
        return f"{section_title} generated content"


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
    assert "<!-- docgen:begin:badges -->" in content
    assert "## Table of Contents" in content
    assert "## Quick Start" in content
    assert "pip install -r requirements.txt" in content
    assert "python -m pytest" in content
    assert "docker build" in content

    scorecard_path = repo_root / ".docgen" / "scorecard.json"
    assert scorecard_path.exists()
    data = json.loads(scorecard_path.read_text(encoding="utf-8"))
    assert "score" in data


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


def test_run_init_uses_llm_runner_streaming(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample"
    repo_root.mkdir()
    _seed_sample_repo(repo_root)

    runner = RecordingLLMRunner()
    orchestrator = Orchestrator(llm_runner=runner)
    readme_path = orchestrator.run_init(str(repo_root))

    content = readme_path.read_text(encoding="utf-8")
    assert "generated content" in content
    assert len(runner.calls) == len(DEFAULT_SECTIONS)
    assert all(call["system"] == PromptBuilder.SYSTEM_PROMPT for call in runner.calls)
    assert all(call["max_tokens"] is None for call in runner.calls)


def test_llm_runner_config_changes_are_respected(tmp_path: Path, monkeypatch) -> None:
    stub_instances: list[object] = []

    class StubRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.calls: list[tuple[str, str | None, int | None]] = []
            stub_instances.append(self)

        def run(self, prompt: str, *, system: str | None = None, max_tokens: int | None = None) -> str:
            self.calls.append((prompt, system, max_tokens))
            return "Generated section"

    monkeypatch.setattr("docgen.orchestrator.LLMRunner", StubRunner)

    orchestrator = Orchestrator()

    repo1 = tmp_path / "repo1"
    repo1.mkdir()
    _seed_sample_repo(repo1)
    (repo1 / ".docgen.yml").write_text(
        """
llm:
  runner: ollama
""",
        encoding="utf-8",
    )

    orchestrator.run_init(str(repo1))
    assert len(stub_instances) == 1
    first_runner = stub_instances[0]
    first_call_count = len(first_runner.calls)

    repo2 = tmp_path / "repo2"
    repo2.mkdir()
    _seed_sample_repo(repo2)

    orchestrator.run_init(str(repo2))
    assert len(stub_instances) == 1
    assert len(first_runner.calls) == first_call_count

    repo3 = tmp_path / "repo3"
    repo3.mkdir()
    _seed_sample_repo(repo3)
    (repo3 / ".docgen.yml").write_text(
        """
llm:
  runner: updated-runner
""",
        encoding="utf-8",
    )

    orchestrator.run_init(str(repo3))
    assert len(stub_instances) == 2
    assert stub_instances[1].kwargs.get("executable") == "updated-runner"


class _StubDiffAnalyzer:
    def __init__(self, sections: list[str], changed_files: list[str] | None = None) -> None:
        self.sections = sections
        self.changed_files = changed_files or ["requirements.txt"]
        self.calls: list[tuple[str, str]] = []

    def compute(self, repo_path: str, diff_base: str) -> DiffResult:
        self.calls.append((repo_path, diff_base))
        return DiffResult(base=diff_base, changed_files=self.changed_files, sections=self.sections)


class _StubPromptBuilder:
    def build(self, *args, **kwargs):  # pragma: no cover - not used in tests
        raise NotImplementedError

    def render_sections(self, manifest, signals, sections, contexts=None, **_kwargs):  # type: ignore[no-untyped-def]
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


class _CountingAnalyzer(Analyzer):
    def __init__(self) -> None:
        self.calls = 0

    def supports(self, manifest) -> bool:  # type: ignore[no-untyped-def]
        return True

    def analyze(self, manifest):  # type: ignore[no-untyped-def]
        self.calls += 1
        return [
            Signal(
                name="count",
                value=str(self.calls),
                source="counting",
                metadata={"calls": self.calls},
            )
        ]


def test_run_update_patches_targeted_sections(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample"
    repo_root.mkdir()
    _seed_sample_repo(repo_root)

    init_orchestrator = Orchestrator()
    init_orchestrator.run_init(str(repo_root), skip_validation=True)

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

    assert isinstance(result, UpdateOutcome)
    assert result.path == repo_root.resolve() / "README.md"
    assert not result.dry_run
    assert "UPDATED build_and_test" in result.diff
    content = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "UPDATED build_and_test" in content
    assert "UPDATED features" not in content
    assert publisher.pr_calls, "Expected publish_pr to be invoked"
    pr_call = publisher.pr_calls[0]
    assert pr_call["branch_name"].startswith("docgen/readme-update")

    scorecard_path = repo_root / ".docgen" / "scorecard.json"
    assert scorecard_path.exists()


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

    outcome = orchestrator.run_update(str(repo_root), "origin/main")

    assert isinstance(outcome, UpdateOutcome)
    assert not outcome.dry_run
    content = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "docgen could not populate the Build & Test section automatically." in content


def test_run_update_with_llm_runner_and_custom_builder_falls_back(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample"
    repo_root.mkdir()
    _seed_sample_repo(repo_root)

    Orchestrator().run_init(str(repo_root))

    diff_analyzer = _StubDiffAnalyzer(["build_and_test"])
    runner = RecordingLLMRunner()
    orchestrator = Orchestrator(
        prompt_builder=_StubPromptBuilder(),
        analyzers=[],
        diff_analyzer=diff_analyzer,
        llm_runner=runner,
    )

    outcome = orchestrator.run_update(str(repo_root), "origin/main")

    assert isinstance(outcome, UpdateOutcome)
    assert "UPDATED build_and_test" in outcome.diff
    assert not runner.calls, "Expected LLM runner not to be invoked for custom builders"


def test_run_update_skips_when_no_watched_globs_match(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample"
    repo_root.mkdir()
    _seed_sample_repo(repo_root)

    Orchestrator().run_init(str(repo_root))

    (repo_root / ".docgen.yml").write_text(
        """
ci:
  watched_globs:
    - docs/**
""",
        encoding="utf-8",
    )

    diff_analyzer = _StubDiffAnalyzer(["features"], changed_files=["src/app.py"])
    orchestrator = Orchestrator(
        prompt_builder=_StubPromptBuilder(),
        analyzers=[],
        diff_analyzer=diff_analyzer,
    )

    result = orchestrator.run_update(str(repo_root), "origin/main")

    assert result is None


def test_run_update_respects_recursive_watched_globs(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample"
    repo_root.mkdir()
    _seed_sample_repo(repo_root)

    Orchestrator().run_init(str(repo_root))

    (repo_root / ".docgen.yml").write_text(
        """
ci:
  watched_globs:
    - '**/*.py'
""",
        encoding="utf-8",
    )

    diff_analyzer = _StubDiffAnalyzer(["features"], changed_files=["main.py"])
    orchestrator = Orchestrator(
        prompt_builder=_StubPromptBuilder(),
        analyzers=[],
        diff_analyzer=diff_analyzer,
    )

    outcome = orchestrator.run_update(str(repo_root), "origin/main")

    assert isinstance(outcome, UpdateOutcome)
    assert outcome.path == repo_root.resolve() / "README.md"
    assert "UPDATED features" in outcome.diff
    content = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "UPDATED features" in content


def test_run_update_supports_dry_run(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample"
    repo_root.mkdir()
    _seed_sample_repo(repo_root)

    Orchestrator().run_init(str(repo_root))

    diff_analyzer = _StubDiffAnalyzer(["features"], changed_files=["src/app.py"])
    orchestrator = Orchestrator(
        prompt_builder=_StubPromptBuilder(),
        analyzers=[],
        diff_analyzer=diff_analyzer,
    )

    outcome = orchestrator.run_update(str(repo_root), "origin/main", dry_run=True)

    assert isinstance(outcome, UpdateOutcome)
    assert outcome.dry_run is True
    assert "UPDATED features" in outcome.diff
    content = (repo_root / "README.md").read_text(encoding="utf-8")
    assert "UPDATED features" not in content


def test_analyzer_cache_reuses_results_between_runs(tmp_path: Path) -> None:
    repo_root = tmp_path / "sample"
    repo_root.mkdir()
    _seed_sample_repo(repo_root)

    counting_analyzer = _CountingAnalyzer()
    init_orchestrator = Orchestrator(analyzers=[counting_analyzer])
    init_orchestrator.run_init(str(repo_root), skip_validation=True)

    assert counting_analyzer.calls == 1

    diff_analyzer = _StubDiffAnalyzer(["features"], changed_files=["src/app.py"])
    cached_analyzer = _CountingAnalyzer()
    update_orchestrator = Orchestrator(
        analyzers=[cached_analyzer],
        diff_analyzer=diff_analyzer,
    )

    outcome = update_orchestrator.run_update(str(repo_root), "origin/main", skip_validation=True)

    assert outcome is None or isinstance(outcome, UpdateOutcome)
    assert cached_analyzer.calls == 0
