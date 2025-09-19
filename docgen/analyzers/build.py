"""Build system analyzer implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from .base import Analyzer
from ..models import RepoManifest, Signal


class BuildAnalyzer(Analyzer):
    """Detects build systems and associated developer workflows."""

    _PY_BUILD_FILES = {
        "pyproject.toml",
        "setup.cfg",
        "requirements.txt",
    }

    def supports(self, manifest: RepoManifest) -> bool:
        return bool(manifest.files)

    def analyze(self, manifest: RepoManifest) -> Iterable[Signal]:
        root = Path(manifest.root)
        manifest_paths = {file.path for file in manifest.files}
        signals: List[Signal] = []

        python_files = self._PY_BUILD_FILES.intersection(manifest_paths)
        if python_files:
            commands = [
                "python -m venv .venv",
                "source .venv/bin/activate" if not self._is_windows() else ".\\.venv\\Scripts\\activate",
                "python -m pip install -r requirements.txt"
                if "requirements.txt" in manifest_paths
                else "python -m pip install -e .",
            ]
            commands.append("python -m pytest")

            signals.append(
                Signal(
                    name="build.python",
                    value="python",
                    source="build",
                    metadata={
                        "files": sorted(python_files),
                        "commands": commands,
                    },
                )
            )

        # Extend with other build system detections as needed.
        if not signals:
            signals.append(
                Signal(
                    name="build.generic",
                    value="generic",
                    source="build",
                    metadata={"commands": ["# Document build steps here."]},
                )
            )

        return signals

    @staticmethod
    def _is_windows() -> bool:
        from sys import platform

        return platform.startswith("win")
