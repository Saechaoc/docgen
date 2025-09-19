"""Repository scanning and manifest building utilities."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterator

from .models import FileMeta, RepoManifest

_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".docgen",
    "sandbox",
}

_EXCLUDED_FILES = {
    "README.md~",
    ".DS_Store",
    "Thumbs.db",
}

_LANGUAGE_BY_SUFFIX = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cc": "C++",
    ".hh": "C++",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".scala": "Scala",
    ".r": "R",
    ".jl": "Julia",
    ".sh": "Shell",
    ".ps1": "PowerShell",
    ".bat": "Batch",
    ".cmd": "Batch",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
}

_ROLE_RULES: tuple[tuple[str, str], ...] = (
    ("tests", "test"),
    ("test", "test"),
    ("docs", "docs"),
    ("doc", "docs"),
    ("examples", "examples"),
    ("example", "examples"),
    ("config", "config"),
    ("infra", "infra"),
)


def _iter_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in _EXCLUDED_DIRS and not name.startswith(".")
        ]
        for filename in filenames:
            if filename in _EXCLUDED_FILES:
                continue
            path = Path(dirpath, filename)
            yield path


def _detect_language(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in _LANGUAGE_BY_SUFFIX:
        return _LANGUAGE_BY_SUFFIX[suffix]
    return None


def _detect_role(relative_path: str) -> str:
    parts = relative_path.split("/")
    for segment, role in _ROLE_RULES:
        if segment in parts:
            return role
    if relative_path.endswith((".md", ".rst")):
        return "docs"
    if "/tests/" in f"/{relative_path}/":
        return "test"
    return "src"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RepoScanner:
    """Walks the repository to produce a normalized manifest."""

    def scan(self, root: str) -> RepoManifest:
        """Return a manifest describing project files and roles."""
        root_path = Path(root).expanduser().resolve()
        if not root_path.exists():
            raise FileNotFoundError(f"Repository path not found: {root}")
        if not root_path.is_dir():
            raise NotADirectoryError(f"Repository path is not a directory: {root}")

        files: list[FileMeta] = []
        for path in _iter_files(root_path):
            rel_path = path.relative_to(root_path).as_posix()
            language = _detect_language(path)
            role = _detect_role(rel_path)
            size = path.stat().st_size
            file_hash = _hash_file(path)
            files.append(
                FileMeta(
                    path=rel_path,
                    size=size,
                    language=language,
                    role=role,
                    hash=file_hash,
                )
            )

        return RepoManifest(root=str(root_path), files=files)
