"""Analyzer plugin implementations and discovery utilities."""

from __future__ import annotations

from importlib import metadata
from typing import Callable, Iterable, List, Sequence, Set, Type

from .base import Analyzer
from .build import BuildAnalyzer
from .dependencies import DependencyAnalyzer
from .entrypoints import EntryPointAnalyzer
from .language import LanguageAnalyzer
from .patterns import PatternAnalyzer

_ENTRY_POINT_GROUP = "docgen.analyzers"

_BUILTIN_FACTORIES: dict[str, Callable[[], Analyzer]] = {
    "language": LanguageAnalyzer,
    "build": BuildAnalyzer,
    "dependencies": DependencyAnalyzer,
    "entrypoints": EntryPointAnalyzer,
    "patterns": PatternAnalyzer,
}


def discover_analyzers(enabled: Sequence[str] | None = None) -> List[Analyzer]:
    """Return instantiated analyzers, honoring optional enabled names."""

    enabled_set: Set[str] | None = None
    if enabled is not None:
        enabled_set = {name.lower() for name in enabled}

    analyzers: List[Analyzer] = []
    seen: Set[str] = set()

    def _add(name: str, factory: Callable[[], Analyzer]) -> None:
        nonlocal enabled_set
        key = name.lower()
        if enabled_set is not None and key not in enabled_set:
            return
        if key in seen:
            return
        instance = factory()
        if not isinstance(instance, Analyzer):
            raise TypeError(f"Analyzer factory for '{name}' did not return an Analyzer instance")
        analyzers.append(instance)
        seen.add(key)
        if enabled_set is not None:
            enabled_set.discard(key)

    for name, factory in _BUILTIN_FACTORIES.items():
        _add(name, factory)

    for entry in _iter_entry_points():
        name = entry.name
        try:
            loaded = entry.load()
        except Exception as exc:  # pragma: no cover - defensive guard
            raise RuntimeError(f"Failed to load analyzer entry point '{name}': {exc}") from exc

        def _factory(obj: object = loaded) -> Analyzer:
            return _coerce_analyzer(obj)

        _add(name, _factory)

    if enabled_set:
        missing = ", ".join(sorted(enabled_set))
        raise ValueError(f"Unknown analyzers requested: {missing}")

    return analyzers


def _coerce_analyzer(obj: object) -> Analyzer:
    if isinstance(obj, Analyzer):
        return obj
    if isinstance(obj, type) and issubclass(obj, Analyzer):
        return obj()
    if callable(obj):
        instance = obj()
        if isinstance(instance, Analyzer):
            return instance
    raise TypeError("Analyzer entry point must be an Analyzer subclass or factory")


def _iter_entry_points() -> Iterable[metadata.EntryPoint]:
    try:
        entry_points = metadata.entry_points()
    except Exception:  # pragma: no cover - defensive guard
        return []

    if hasattr(entry_points, "select"):
        return entry_points.select(group=_ENTRY_POINT_GROUP)  # type: ignore[return-value]

    return entry_points.get(_ENTRY_POINT_GROUP, [])  # type: ignore[return-value]


__all__ = [
    "discover_analyzers",
    "Analyzer",
]
