"""Tests for docgen.repo_scanner."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from docgen import repo_scanner
from docgen.repo_scanner import RepoScanner


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_builds_manifest_with_roles_and_language(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write(repo_root / "src" / "app.py", "print('hi')\n")
    _write(repo_root / "tests" / "test_app.py", "def test_ok():\n    assert True\n")
    _write(repo_root / "docs" / "overview.md", "# Overview\n")
    _write(repo_root / "config" / "settings.yaml", "debug: true\n")
    _write(repo_root / "infra" / "Dockerfile", "FROM python:3.11-slim\n")
    _write(repo_root / ".venv" / "should_ignore.py", "print('nope')\n")

    scanner = RepoScanner()
    manifest = scanner.scan(str(repo_root))

    assert manifest.root == str(repo_root.resolve())
    paths = {file.path: file for file in manifest.files}

    assert "src/app.py" in paths
    assert paths["src/app.py"].language == "Python"
    assert paths["src/app.py"].role == "src"

    assert paths["tests/test_app.py"].role == "test"
    assert paths["docs/overview.md"].role == "docs"
    assert paths["config/settings.yaml"].role == "config"
    assert paths["infra/Dockerfile"].role == "infra"

    assert ".venv/should_ignore.py" not in paths

    file = paths["src/app.py"]
    expected_hash = sha256((repo_root / "src" / "app.py").read_bytes()).hexdigest()
    assert file.hash == expected_hash


def test_scan_rejects_missing_directory(tmp_path: Path) -> None:
    scanner = RepoScanner()
    missing = tmp_path / "missing"
    try:
        scanner.scan(str(missing))
    except FileNotFoundError as exc:
        assert str(missing) in str(exc)
    else:  # pragma: no cover - defensive guard
        raise AssertionError(
            "Expected FileNotFoundError when scanning missing directory"
        )


def test_scan_respects_gitignore(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write(repo_root / ".gitignore", "build/\n*.log\n")
    _write(repo_root / "src" / "main.py", "print('ok')\n")
    (repo_root / "build").mkdir()
    _write(repo_root / "build" / "artifact.txt", "binary data\n")
    _write(repo_root / "notes.log", "ignore me\n")

    manifest = RepoScanner().scan(str(repo_root))
    paths = {file.path for file in manifest.files}

    assert "src/main.py" in paths
    assert "build/artifact.txt" not in paths
    assert "notes.log" not in paths


def test_scan_respects_docgen_exclude_paths(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write(
        repo_root / ".docgen.yml",
        "exclude_paths:\n  - data/\n  - '*.generated'\n",
    )
    _write(repo_root / "src" / "main.py", "print('ok')\n")
    _write(repo_root / "data" / "ignored.txt", "secret\n")
    _write(repo_root / "report.generated", "generated output\n")

    manifest = RepoScanner().scan(str(repo_root))
    paths = {file.path for file in manifest.files}

    assert "src/main.py" in paths
    assert "data/ignored.txt" not in paths
    assert "report.generated" not in paths


def test_scan_writes_manifest_cache(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write(repo_root / "src" / "main.py", "print('ok')\n")

    RepoScanner().scan(str(repo_root))

    cache_path = repo_root / ".docgen" / "manifest_cache.json"
    assert cache_path.exists()

    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload.get("version") == 1
    files = payload.get("files", {})
    assert "src/main.py" in files


def test_scan_reuses_cache_for_unchanged_files(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    target = repo_root / "src" / "main.py"
    _write(target, "print('ok')\n")

    RepoScanner().scan(str(repo_root))

    def _fail_hash(path: Path) -> str:
        raise AssertionError("Hash should have been reused from cache")

    monkeypatch.setattr(repo_scanner, "_hash_file", _fail_hash)

    RepoScanner().scan(str(repo_root))
