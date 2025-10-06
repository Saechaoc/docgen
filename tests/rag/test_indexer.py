"""Tests for the RAG indexer."""

from __future__ import annotations

from pathlib import Path

from docgen.rag.indexer import RAGIndexer
from docgen.repo_scanner import RepoScanner


def _seed_repo(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "overview.md").write_text("# Overview\nThe service handles requests.\n", encoding="utf-8")
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "main.py").write_text(
        """Entrypoint.\n\nif __name__ == '__main__':\n    print('hi')\n""",
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Sample\nExisting description.\n", encoding="utf-8")


def test_rag_indexer_builds_contexts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)

    manifest = RepoScanner().scan(str(repo))
    index = RAGIndexer(top_source_files=5).build(manifest)

    assert index.contexts["architecture"], "Expected architecture context snippets"
    assert index.contexts["features"], "Expected features context snippets"
    assert index.store_path.exists(), "Embedding index should be persisted"


def test_rag_indexer_refreshes_contexts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)

    scanner = RepoScanner()
    indexer = RAGIndexer(top_source_files=5)

    manifest = scanner.scan(str(repo))
    indexer.build(manifest)

    (repo / "README.md").write_text("# Sample\nUpdated description for second run.\n", encoding="utf-8")

    manifest = scanner.scan(str(repo))
    second_index = indexer.build(manifest)
    intro_context = " ".join(second_index.contexts["intro"])

    assert "Updated description for second run" in intro_context
    assert "Existing description" not in intro_context
