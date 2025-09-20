"""Tests for structure analyzer."""

from __future__ import annotations

from pathlib import Path

from docgen.analyzers.structure import StructureAnalyzer
from docgen.repo_scanner import RepoScanner


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_structure_analyzer_detects_fastapi_sequence(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(
        repo / "app" / "api.py",
        """
from fastapi import FastAPI
import requests

app = FastAPI()

@app.get("/login")
async def login():
    resp = requests.post("https://auth.service/token")
    return {"token": resp.json()}
""",
    )

    manifest = RepoScanner().scan(str(repo))
    signals = list(StructureAnalyzer().analyze(manifest))

    api_signal = next(sig for sig in signals if sig.name == "architecture.api")
    assert api_signal.metadata["framework"] == "FastAPI"
    sequence = api_signal.metadata["sequence"]
    assert sequence[0]["message"] == "GET /login"
    assert any(step["to"] == "External service" for step in sequence)


def test_structure_analyzer_summarises_modules(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo / "services" / "svc.py", "print('hi')\n")
    _write(repo / "services" / "__init__.py", "")
    _write(repo / "docs" / "readme.md", "# Docs\n")

    manifest = RepoScanner().scan(str(repo))
    signals = list(StructureAnalyzer().analyze(manifest))

    modules = next(sig for sig in signals if sig.name == "architecture.modules")
    module_names = [module["name"] for module in modules.metadata["modules"]]
    assert "services" in module_names
