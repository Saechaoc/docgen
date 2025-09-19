"""Dependency analyzer implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from .base import Analyzer
from .utils import (
    load_java_dependencies,
    load_node_dependencies,
    load_python_dependencies,
)
from ..models import RepoManifest, Signal


class DependencyAnalyzer(Analyzer):
    """Extracts notable dependencies from manifest files."""

    PYTHON_FILES = {"requirements.txt", "pyproject.toml"}
    NODE_FILES = {"package.json"}
    JAVA_FILES = {"pom.xml", "build.gradle", "build.gradle.kts"}

    def supports(self, manifest: RepoManifest) -> bool:
        manifest_paths = {file.path for file in manifest.files}
        return bool(
            self.PYTHON_FILES.intersection(manifest_paths)
            or self.NODE_FILES.intersection(manifest_paths)
            or self.JAVA_FILES.intersection(manifest_paths)
        )

    def analyze(self, manifest: RepoManifest) -> Iterable[Signal]:
        root = Path(manifest.root)
        signals: List[Signal] = []

        python_packages = load_python_dependencies(root)
        if python_packages:
            signals.append(
                Signal(
                    name="dependencies.python",
                    value=", ".join(python_packages[:5]),
                    source="dependencies",
                    metadata={"packages": python_packages},
                )
            )

        node_deps = load_node_dependencies(root)
        runtime = node_deps.get("dependencies", [])
        dev = node_deps.get("devDependencies", [])
        if runtime or dev:
            summary = runtime[:5] if runtime else dev[:5]
            signals.append(
                Signal(
                    name="dependencies.node",
                    value=", ".join(summary),
                    source="dependencies",
                    metadata=node_deps,
                )
            )

        java_deps = load_java_dependencies(root)
        if java_deps:
            signals.append(
                Signal(
                    name="dependencies.java",
                    value=", ".join(java_deps[:5]),
                    source="dependencies",
                    metadata={"packages": java_deps},
                )
            )

        return signals
