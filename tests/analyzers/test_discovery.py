"""Tests for analyzer discovery utilities."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from docgen.analyzers import Analyzer, discover_analyzers
from docgen.analyzers.language import LanguageAnalyzer


class DummyAnalyzer(Analyzer):
    """Test analyzer used for plugin discovery validation."""

    def supports(self, manifest):  # pragma: no cover - unused
        return False

    def analyze(self, manifest):  # pragma: no cover - unused
        return []


def test_discover_analyzers_returns_builtin_analyzers() -> None:
    analyzers = discover_analyzers()
    classes = {type(analyzer) for analyzer in analyzers}
    assert LanguageAnalyzer in classes
    assert len(analyzers) >= 3  # language, build, dependencies


def test_discover_analyzers_respects_enabled_filter() -> None:
    analyzers = discover_analyzers(["language"])
    assert len(analyzers) == 1
    assert isinstance(analyzers[0], LanguageAnalyzer)


def test_discover_analyzers_loads_entry_points(monkeypatch) -> None:
    dummy_entry = SimpleNamespace(
        name="dummy",
        load=lambda: DummyAnalyzer,
    )

    class DummyEntryPoints(list):
        def select(self, **kwargs):
            if kwargs.get("group") == "docgen.analyzers":
                return self
            return []

    monkeypatch.setattr(
        "docgen.analyzers.metadata.entry_points",
        lambda: DummyEntryPoints([dummy_entry]),
        raising=False,
    )

    analyzers = discover_analyzers(["dummy"])
    assert len(analyzers) == 1
    assert isinstance(analyzers[0], DummyAnalyzer)


def test_discover_analyzers_raises_for_unknown_name() -> None:
    with pytest.raises(ValueError):
        discover_analyzers(["does-not-exist"])
