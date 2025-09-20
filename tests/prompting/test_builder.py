"""Tests for the prompt builder."""

from __future__ import annotations

from pathlib import Path

from docgen.analyzers.build import BuildAnalyzer
from docgen.analyzers.dependencies import DependencyAnalyzer
from docgen.analyzers.language import LanguageAnalyzer
from docgen.prompting.builder import PromptBuilder
from docgen.repo_scanner import RepoScanner


def _seed_repo(root: Path) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (root / "src" / "index.js").write_text("console.log('hi');\n", encoding="utf-8")
    (root / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (root / "package.json").write_text(
        '{"name": "demo", "dependencies": {"express": "4"}}\n', encoding="utf-8"
    )


def test_prompt_builder_renders_marked_sections(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)

    manifest = RepoScanner().scan(str(repo))
    analyzers = [LanguageAnalyzer(), BuildAnalyzer(), DependencyAnalyzer()]
    signals = []
    for analyzer in analyzers:
        signals.extend(analyzer.analyze(manifest))

    builder = PromptBuilder()
    readme = builder.build(manifest, signals)

    assert "<!-- docgen:begin:intro -->" in readme
    assert "<!-- docgen:begin:features -->" in readme
    assert "<!-- docgen:toc -->" in readme


def test_prompt_builder_render_sections_subset(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)

    manifest = RepoScanner().scan(str(repo))
    analyzers = [LanguageAnalyzer(), BuildAnalyzer(), DependencyAnalyzer()]
    signals = []
    for analyzer in analyzers:
        signals.extend(analyzer.analyze(manifest))

    builder = PromptBuilder()
    sections = builder.render_sections(manifest, signals, ["intro", "deployment"])

    assert set(sections) == {"intro", "deployment"}
    assert "docgen" in sections["intro"].body
    assert sections["deployment"].body.strip()
