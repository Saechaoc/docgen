"""Tests for the entrypoint analyzer."""

from __future__ import annotations

from pathlib import Path

from docgen.analyzers.entrypoints import EntryPointAnalyzer
from docgen.repo_scanner import RepoScanner


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_entrypoint_detects_fastapi(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "app" / "main.py", "from fastapi import FastAPI\napp = FastAPI()\n")

    manifest = RepoScanner().scan(str(repo))
    signals = list(EntryPointAnalyzer().analyze(manifest))

    commands = [sig.metadata.get("command") for sig in signals if sig.metadata]
    assert "uvicorn app.main:app --reload" in commands


def test_entrypoint_detects_node_scripts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(
        repo / "package.json",
        """
{
  "name": "demo",
  "scripts": {
    "dev": "next dev"
  }
}
""",
    )
    _write(repo / "pnpm-lock.yaml", "")

    manifest = RepoScanner().scan(str(repo))
    signals = list(EntryPointAnalyzer().analyze(manifest))

    commands = [sig.metadata.get("command") for sig in signals if sig.metadata]
    assert "pnpm dev" in commands


def test_entrypoint_detects_spring_boot(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "pom.xml", "<project></project>\n")
    _write(repo / "mvnw", "#!/bin/sh\n")
    _write(
        repo / "src" / "main" / "java" / "DemoApplication.java",
        """
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class DemoApplication {}
""",
    )

    manifest = RepoScanner().scan(str(repo))
    signals = list(EntryPointAnalyzer().analyze(manifest))
    commands = [sig.metadata.get("command") for sig in signals if sig.metadata]

    assert "./mvnw spring-boot:run" in commands
