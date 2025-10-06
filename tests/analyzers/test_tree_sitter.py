"""Tests for the tree-sitter analyzer."""

from __future__ import annotations

from pathlib import Path

import pytest

from docgen.analyzers.tree_sitter import TREE_SITTER_AVAILABLE, TreeSitterAnalyzer
from docgen.models import FileMeta, RepoManifest


def _manifest(
    tmp_path: Path, filename: str, content: str, language: str | None = None
) -> RepoManifest:
    file_path = tmp_path / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    meta = FileMeta(
        path=filename, size=len(content), language=language, role="src", hash="hash"
    )
    return RepoManifest(root=str(tmp_path), files=[meta])


def test_tree_sitter_analyzer_disabled_when_not_available() -> None:
    analyzer = TreeSitterAnalyzer(enabled=False)
    manifest = RepoManifest(root="/tmp", files=[])
    assert analyzer.supports(manifest) is False
    assert list(analyzer.analyze(manifest)) == []


@pytest.mark.skipif(
    not TREE_SITTER_AVAILABLE, reason="tree_sitter_languages not installed"
)
def test_tree_sitter_analyzer_extracts_python_symbols(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        "src/example.py",
        """
class Example:
    def method(self, value):
        return value

def helper(x):
    return x * 2
""",
        language="Python",
    )
    analyzer = TreeSitterAnalyzer()
    assert analyzer.supports(manifest)
    signals = list(analyzer.analyze(manifest))
    names = {signal.value for signal in signals}
    assert {"Example", "method", "helper"}.issubset(names)
