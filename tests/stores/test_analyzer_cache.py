"""Tests for the analyzer cache store."""

from __future__ import annotations

from pathlib import Path

from docgen.models import Signal
from docgen.stores import AnalyzerCache


def test_analyzer_cache_round_trip(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.json"
    cache = AnalyzerCache(cache_path)
    signals = [
        Signal(name="lang", value="Python", source="language", metadata={"files": 3})
    ]
    cache.store(
        "language",
        signature="sig-1",
        fingerprint="fp-abc",
        signals=signals,
    )
    cache.persist()

    loaded = AnalyzerCache(cache_path)
    reuse = loaded.get("language", signature="sig-1", fingerprint="fp-abc")

    assert reuse is not None
    assert reuse == signals


def test_analyzer_cache_invalidates_on_signature_change(tmp_path: Path) -> None:
    cache = AnalyzerCache(tmp_path / "cache.json")
    signal = Signal(name="build", value="poetry", source="build", metadata={})
    cache.store("build", signature="sig-1", fingerprint="fp", signals=[signal])

    assert cache.get("build", signature="sig-1", fingerprint="fp") is not None
    assert cache.get("build", signature="sig-2", fingerprint="fp") is None
    assert cache.get("build", signature="sig-1", fingerprint="fp-changed") is None


def test_analyzer_cache_prune_removes_unused(tmp_path: Path) -> None:
    cache = AnalyzerCache(tmp_path / "cache.json")
    cache.store("a", signature="s", fingerprint="fp", signals=[])
    cache.store("b", signature="s", fingerprint="fp", signals=[])

    cache.prune(["a"])
    cache.persist()

    reloaded = AnalyzerCache(tmp_path / "cache.json")
    assert reloaded.get("a", signature="s", fingerprint="fp") == []
    assert reloaded.get("b", signature="s", fingerprint="fp") is None
