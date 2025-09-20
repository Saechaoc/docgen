"""Analyzer that infers repository architecture constructs for README init."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

from .base import Analyzer
from .endpoints.core import DetectorRegistry
from .endpoints.detectors import ExpressDetector, FastAPIDetector, SpecDetector, SpringDetector
from ..models import RepoManifest, Signal

_PY_MODEL_CLASS = re.compile(r"class\s+(\w+)\(([^)]*)\):")


@dataclass
class _FileSummary:
    count: int = 0
    roles: set[str] = None  # type: ignore[assignment]
    languages: set[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.roles is None:
            self.roles = set()
        if self.languages is None:
            self.languages = set()


class StructureAnalyzer(Analyzer):
    """Derives architectural signals from source files and layout."""

    _ENDPOINT_DETECTORS: Sequence = (
        SpecDetector(),
        FastAPIDetector(),
        ExpressDetector(),
        SpringDetector(),
    )

    def supports(self, manifest: RepoManifest) -> bool:
        return bool(manifest.files)

    def analyze(self, manifest: RepoManifest) -> Iterable[Signal]:
        signals: List[Signal] = []
        modules = self._summarise_modules(manifest)
        if modules:
            signals.append(
                Signal(
                    name="architecture.modules",
                    value="modules",
                    source="structure",
                    metadata={"modules": modules},
                )
            )

        signals.extend(self._detect_api_endpoints(manifest))
        signals.extend(self._detect_entities(manifest))
        return signals

    def _summarise_modules(self, manifest: RepoManifest) -> List[Dict[str, object]]:
        summaries: Dict[str, _FileSummary] = defaultdict(_FileSummary)
        for meta in manifest.files:
            parts = meta.path.split("/")
            top = parts[0]
            summary = summaries[top]
            summary.count += 1
            summary.roles.add(meta.role)
            if meta.language:
                summary.languages.add(meta.language)

        result: List[Dict[str, object]] = []
        for name, summary in sorted(summaries.items()):
            result.append(
                {
                    "name": name,
                    "files": summary.count,
                    "roles": sorted(summary.roles),
                    "languages": sorted(summary.languages),
                }
            )
        return result

    def _detect_api_endpoints(self, manifest: RepoManifest) -> List[Signal]:
        registry = DetectorRegistry(self._ENDPOINT_DETECTORS)
        endpoints = registry.run(manifest)
        signals: List[Signal] = []
        for endpoint in endpoints:
            role = f"{endpoint.framework} endpoint" if endpoint.framework else "Endpoint"
            sequence = self._build_sequence(role, endpoint.method, endpoint.path)
            signals.append(
                Signal(
                    name="architecture.api",
                    value=f"{endpoint.method} {endpoint.path}",
                    source="structure",
                    metadata={
                        "framework": endpoint.framework,
                        "method": endpoint.method,
                        "path": endpoint.path,
                        "file": endpoint.file,
                        "line": endpoint.line,
                        "language": endpoint.language,
                        "confidence": endpoint.confidence,
                        "sequence": sequence,
                    },
                )
            )
        return signals

    def _detect_entities(self, manifest: RepoManifest) -> List[Signal]:
        root = Path(manifest.root)
        signals: List[Signal] = []

        for meta in manifest.files:
            if meta.language != "Python" or not meta.path.endswith(".py"):
                continue
            file_path = root / meta.path
            try:
                text = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for class_match in _PY_MODEL_CLASS.finditer(text):
                name, bases = class_match.groups()
                lower_bases = bases.lower()
                if "basemodel" in lower_bases or "models.model" in lower_bases or "sqlalchemy" in lower_bases or "declarative_base" in lower_bases or "Base" in bases:
                    fields = self._extract_class_fields(text, class_match.end())
                    signals.append(
                        Signal(
                            name="architecture.entity",
                            value=name,
                            source="structure",
                            metadata={
                                "name": name,
                                "bases": [base.strip() for base in bases.split(",")],
                                "file": meta.path,
                                "fields": fields,
                            },
                        )
                    )
        return signals

    @staticmethod
    def _extract_class_fields(text: str, position: int) -> List[str]:
        body = text[position:]
        fields: List[str] = []
        for match in re.finditer(r"^(\s{4}|\t)(\w+)\s*:\s*([^=\n]+)", body, flags=re.MULTILINE):
            name = match.group(2)
            annotation = match.group(3).strip()
            fields.append(f"{name}: {annotation}")
        return fields

    @staticmethod
    def _build_sequence(role: str, method: str, path: str) -> List[Dict[str, str]]:
        return [
            {"from": "Client", "to": role, "message": f"{method} {path}"},
            {"from": role, "to": "Client", "message": "Response"},
        ]


__all__ = ["StructureAnalyzer"]
