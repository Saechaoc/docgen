"""Dependency analyzer implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from .base import Analyzer
from ..models import RepoManifest, Signal


class DependencyAnalyzer(Analyzer):
    """Extracts notable dependencies from manifest files."""

    def supports(self, manifest: RepoManifest) -> bool:
        manifest_paths = {file.path for file in manifest.files}
        return any(
            path in manifest_paths for path in ("requirements.txt", "pyproject.toml", "package.json")
        )

    def analyze(self, manifest: RepoManifest) -> Iterable[Signal]:
        root = Path(manifest.root)
        signals: List[Signal] = []

        requirements = root / "requirements.txt"
        if requirements.exists():
            packages = self._parse_requirements(requirements)
            if packages:
                signals.append(
                    Signal(
                        name="dependencies.python",
                        value=", ".join(packages[:5]),
                        source="dependencies",
                        metadata={"packages": packages},
                    )
                )

        # Extend for other ecosystems when needed.
        return signals

    @staticmethod
    def _parse_requirements(path: Path) -> List[str]:
        packages: List[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "-r")):
                continue
            packages.append(stripped)
        return packages
