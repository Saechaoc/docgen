"""Analyzer that infers repository architecture constructs for README init."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from .base import Analyzer
from ..models import RepoManifest, Signal

_FASTAPI_DECORATOR = re.compile(r"@(\w+)\.(get|post|put|delete|patch)\((['\"])([^'\"]+)\3")
_EXPRESS_ROUTE = re.compile(r"(app|router)\.(get|post|put|delete|patch)\((['\"])([^'\"]+)\3")
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

        api_signals = self._detect_api_endpoints(manifest)
        signals.extend(api_signals)

        entity_signals = self._detect_entities(manifest)
        signals.extend(entity_signals)

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
        root = Path(manifest.root)
        api_signals: List[Signal] = []

        for meta in manifest.files:
            file_path = root / meta.path
            if not file_path.exists() or file_path.is_dir():
                continue
            try:
                text = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            if meta.language == "Python":
                api_signals.extend(self._extract_fastapi_endpoints(meta.path, text))
            elif meta.language in {"JavaScript", "TypeScript"}:
                api_signals.extend(self._extract_express_endpoints(meta.path, text))

        return api_signals

    def _extract_fastapi_endpoints(self, path: str, text: str) -> List[Signal]:
        signals: List[Signal] = []
        for match in _FASTAPI_DECORATOR.finditer(text):
            router_name, method, _, route = match.groups()
            function_name = self._find_next_function_name(text, match.end())
            external_call = self._detect_external_call(text, match.end())
            sequence = self._build_sequence("FastAPI endpoint", method.upper(), route, external_call)
            signals.append(
                Signal(
                    name="architecture.api",
                    value=f"{method.upper()} {route}",
                    source="structure",
                    metadata={
                        "framework": "FastAPI",
                        "router": router_name,
                        "method": method.upper(),
                        "path": route,
                        "handler": function_name,
                        "file": path,
                        "external_call": external_call,
                        "sequence": sequence,
                    },
                )
            )
        return signals

    def _extract_express_endpoints(self, path: str, text: str) -> List[Signal]:
        signals: List[Signal] = []
        for match in _EXPRESS_ROUTE.finditer(text):
            router_name, method, _, route = match.groups()
            external_call = self._detect_external_call(text, match.end())
            sequence = self._build_sequence("Express route", method.upper(), route, external_call)
            signals.append(
                Signal(
                    name="architecture.api",
                    value=f"{method.upper()} {route}",
                    source="structure",
                    metadata={
                        "framework": "Express",
                        "router": router_name,
                        "method": method.upper(),
                        "path": route,
                        "file": path,
                        "external_call": external_call,
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
    def _find_next_function_name(text: str, position: int) -> str | None:
        func_match = re.search(r"def\s+(\w+)\s*\(", text[position:])
        if func_match:
            return func_match.group(1)
        return None

    @staticmethod
    def _detect_external_call(text: str, position: int) -> str | None:
        snippet = text[position:]
        if "requests." in snippet or "httpx." in snippet:
            return "External HTTP call"
        if "asyncio" in snippet and "gather" in snippet:
            return "Async orchestration"
        if "session." in snippet or "db." in snippet:
            return "Database interaction"
        return None

    @staticmethod
    def _build_sequence(role: str, method: str, path: str, external_call: str | None) -> List[Dict[str, str]]:
        steps = [
            {
                "from": "Client",
                "to": role,
                "message": f"{method} {path}",
            }
        ]
        if external_call:
            target = 'External service' if 'HTTP' in external_call else 'Database'
            steps.append({
                'from': role,
                'to': target,
                'message': external_call,
            })
            steps.append({
                'from': target,
                'to': role,
                'message': 'Response',
            })
        steps.append({
            'from': role,
            'to': 'Client',
            'message': 'Response',
        })
        return steps


__all__ = ['StructureAnalyzer']

