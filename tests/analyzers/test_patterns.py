"""Tests for the pattern analyzer."""

from __future__ import annotations

from pathlib import Path

from docgen.analyzers.patterns import PatternAnalyzer
from docgen.repo_scanner import RepoScanner


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_pattern_analyzer_detects_docker(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "Dockerfile", "FROM python:3.11-slim\n")
    _write(repo / "docker-compose.yml", "version: '3'\n")

    manifest = RepoScanner().scan(str(repo))
    signals = list(PatternAnalyzer().analyze(manifest))

    container = next((s for s in signals if s.name == "pattern.containerization"), None)
    assert container is not None
    assert "docker compose up" in container.metadata.get("quickstart", [])


def test_pattern_analyzer_detects_ci_and_monorepo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / ".github" / "workflows" / "ci.yml", "name: CI\n")
    _write(repo / "packages" / "svc-a" / "package.json", "{}\n")
    _write(repo / "services" / "svc-b" / "package.json", "{}\n")

    manifest = RepoScanner().scan(str(repo))
    signals = list(PatternAnalyzer().analyze(manifest))

    ci = next((s for s in signals if s.name == "pattern.ci"), None)
    monorepo = next((s for s in signals if s.name == "pattern.monorepo"), None)
    assert ci is not None
    assert monorepo is not None
