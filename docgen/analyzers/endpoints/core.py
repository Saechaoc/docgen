"""Shared endpoint detection helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Protocol, Sequence, Tuple


@dataclass(frozen=True)
class Endpoint:
    """Normalized representation of an HTTP endpoint."""

    method: str
    path: str
    file: str
    line: Optional[int] = None
    framework: Optional[str] = None
    language: Optional[str] = None
    confidence: float = 1.0


class EndpointDetector(Protocol):
    """Contract for detectors that emit endpoints from a manifest."""

    def supports_repo(self, manifest) -> bool:  # noqa: ANN001 - typed dynamically
        ...

    def extract(
        self, manifest
    ) -> Iterable[Endpoint]:  # noqa: ANN001 - typed dynamically
        ...


_PARAM_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"/:([A-Za-z_][A-Za-z0-9_]*)"), r"/{\1}"),
    (
        re.compile(r"/<(?:(?:[A-Za-z_][A-Za-z0-9_]*):)?([A-Za-z_][A-Za-z0-9_]*)>"),
        r"/{\1}",
    ),
    (re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\s*:\s*[^}]+\}"), r"{\1}"),
    (re.compile(r"\(\?P<([A-Za-z_][A-Za-z0-9_]*)>[^)]+\)"), r"{\1}"),
]


def normalize_path(path: str) -> str:
    """Return a canonical representation for endpoint paths."""
    if not path:
        return "/"
    result = path.strip()
    if not result.startswith("/"):
        result = "/" + result
    for pattern, replacement in _PARAM_PATTERNS:
        result = pattern.sub(replacement, result)
    result = re.sub(r"/{2,}", "/", result)
    if len(result) > 1 and result.endswith("/"):
        result = result[:-1]
    return result or "/"


def join_paths(prefix: str, route: str) -> str:
    """Combine class-level and method-level paths."""
    prefix_norm = normalize_path(prefix) if prefix else ""
    route_norm = normalize_path(route)
    if not prefix_norm:
        return route_norm
    if route_norm == "/":
        return prefix_norm
    combined = f"{prefix_norm}{route_norm}"
    return normalize_path(combined)


def method_upper(value: str) -> str:
    """Normalize HTTP verbs to uppercase."""
    return (value or "").strip().upper()


def line_of(text: str, index: int) -> int:
    """Return 1-based line number for a character index."""
    return text.count("\n", 0, index) + 1


def pick_higher_confidence(existing: Endpoint, new: Endpoint) -> Endpoint:
    """Choose the endpoint with higher confidence, preferring specs when equal."""
    if new.confidence > existing.confidence:
        return new
    if new.confidence < existing.confidence:
        return existing
    rank = {"spec": 3, "framework": 2, "heuristic": 1}
    existing_rank = rank.get((existing.framework or "").lower(), 0)
    new_rank = rank.get((new.framework or "").lower(), 0)
    return new if new_rank > existing_rank else existing


class DetectorRegistry:
    """Executes endpoint detectors and deduplicates outputs."""

    def __init__(self, detectors: Sequence[EndpointDetector]) -> None:
        self._detectors = list(detectors)

    def run(self, manifest) -> List[Endpoint]:  # noqa: ANN001 - dynamic type
        results: Dict[Tuple[str, str], Endpoint] = {}
        for detector in self._detectors:
            if not detector.supports_repo(manifest):
                continue
            for endpoint in detector.extract(manifest):
                method = method_upper(endpoint.method)
                path = normalize_path(endpoint.path)
                normalized = Endpoint(
                    method=method,
                    path=path,
                    file=endpoint.file,
                    line=endpoint.line,
                    framework=endpoint.framework,
                    language=endpoint.language,
                    confidence=endpoint.confidence,
                )
                key = (method, path)
                if key in results:
                    results[key] = pick_higher_confidence(results[key], normalized)
                else:
                    results[key] = normalized
        return sorted(results.values(), key=lambda ep: (ep.path, ep.method))


__all__ = [
    "Endpoint",
    "EndpointDetector",
    "DetectorRegistry",
    "join_paths",
    "line_of",
]
