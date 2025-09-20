"""Helper utilities for constructing temporary repositories in tests."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Mapping

from docgen.repo_scanner import RepoScanner
from docgen.models import RepoManifest


class RepoBuilder:
    """Utility for writing files into a throwaway repository and rescanning it."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "repo"
        self.root.mkdir()
        self._scanner = RepoScanner()

    def write(self, files: Mapping[str, str]) -> None:
        """Write `path -> contents` entries into the repository."""
        for relative, content in files.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            normalised = textwrap.dedent(content).lstrip("\n")
            path.write_text(normalised, encoding="utf-8")

    def scan(self) -> RepoManifest:
        """Return a fresh manifest of the repository contents."""
        return self._scanner.scan(str(self.root))

    def path(self) -> Path:
        """Return the repository root path."""
        return self.root


__all__ = ["RepoBuilder"]
