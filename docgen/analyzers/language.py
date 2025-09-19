"""Language-specific analyzer implementation."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, List

from .base import Analyzer
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

        return [
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
