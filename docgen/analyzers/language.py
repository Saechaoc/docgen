"""Language-specific analyzer implementation."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List

from .base import Analyzer
from .utils import (
    detect_java_frameworks,
    detect_node_frameworks,
    detect_python_frameworks,
    load_java_dependencies,
    load_node_dependencies,
    load_python_dependencies,
)
from ..models import RepoManifest, Signal


class LanguageAnalyzer(Analyzer):
    """Detects frameworks and idioms for supported languages."""

    def supports(self, manifest: RepoManifest) -> bool:
        return bool(manifest.files)

    def analyze(self, manifest: RepoManifest) -> Iterable[Signal]:
        languages: List[str] = [
            file.language for file in manifest.files if file.language is not None
        ]
        if not languages:
            return []

        counts = Counter(languages)
        ordered = [language for language, _ in counts.most_common()]
        primary = ordered[0]

        root = Path(manifest.root)
        frameworks = self._detect_frameworks(root)

        signals: List[Signal] = [
            Signal(
                name="language.primary",
                value=primary,
                source="language",
                metadata={"counts": dict(counts)},
            ),
            Signal(
                name="language.all",
                value=", ".join(ordered),
                source="language",
                metadata={"languages": ordered, "counts": dict(counts)},
            ),
        ]

        if frameworks:
            for language, items in frameworks.items():
                signals.append(
                    Signal(
                        name=f"language.frameworks.{language.lower().replace(' ', '_')}",
                        value=", ".join(items),
                        source="language",
                        metadata={"language": language, "frameworks": items},
                    )
                )
            signals.append(
                Signal(
                    name="language.frameworks",
                    value=", ".join(
                        f"{lang}: {', '.join(items)}" for lang, items in frameworks.items()
                    ),
                    source="language",
                    metadata={"frameworks": frameworks},
                )
            )

        return signals

    def _detect_frameworks(self, root: Path) -> Dict[str, List[str]]:
        frameworks: Dict[str, List[str]] = {}

        python_packages = load_python_dependencies(root)
        python_frameworks = detect_python_frameworks(python_packages)
        if python_frameworks:
            frameworks["Python"] = python_frameworks

        node_dependencies = load_node_dependencies(root)
        node_frameworks = detect_node_frameworks(node_dependencies)
        if node_frameworks:
            frameworks["JavaScript"] = node_frameworks

        java_dependencies = load_java_dependencies(root)
        java_frameworks = detect_java_frameworks(java_dependencies)
        if java_frameworks:
            frameworks["Java"] = java_frameworks

        return frameworks
