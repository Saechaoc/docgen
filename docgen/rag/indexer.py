"""Index builder for minimal retrieval augmented generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set
import hashlib

from ..models import RepoManifest
from ..repo_scanner import FileMeta
from .constants import SECTION_TAGS, TAG_SECTIONS
from .embedder import LocalEmbedder
from .store import EmbeddingStore


@dataclass
class RAGIndex:
    """Holds contexts for README sections and index metadata."""

    contexts: Dict[str, List[str]]
    store_path: Path


class RAGIndexer:
    """Builds a lightweight embedding index for README generation."""

    def __init__(self, *, embedder: LocalEmbedder | None = None, top_source_files: int = 20) -> None:
        self.embedder = embedder or LocalEmbedder()
        self.top_source_files = top_source_files

    def build(self, manifest: RepoManifest, *, sections: Sequence[str] | None = None) -> RAGIndex:
        target_sections = list(sections) if sections else list(SECTION_TAGS.keys())
        root = Path(manifest.root)
        store_path = root / ".docgen" / "embeddings.json"
        store = EmbeddingStore(store_path, load_existing=True)

        contexts: Dict[str, List[str]] = {section: [] for section in target_sections}

        meta_lookup = {file.path: file for file in manifest.files}
        visited_paths: Set[str] = set()

        self._index_readme(root, store, meta_lookup, visited_paths)
        self._index_docs(manifest.files, root, store, visited_paths)
        self._index_source_files(manifest.files, root, store, visited_paths)

        for existing in list(store.paths()):
            if existing not in visited_paths:
                store.remove_path(existing)

        store.persist()

        for section in target_sections:
            snippets = [entry["text"] for entry in store.query(section, top_k=3)]
            contexts[section] = [snippet.strip() for snippet in snippets if snippet.strip()]

        return RAGIndex(contexts=contexts, store_path=store_path)

    # ------------------------------------------------------------------
    # Index helpers

    def _index_readme(
        self,
        root: Path,
        store: EmbeddingStore,
        meta_lookup: Dict[str, FileMeta],
        visited_paths: Set[str],
    ) -> None:
        readme_path = root / "README.md"
        if not readme_path.exists():
            return
        text = _read_text(readme_path)
        if not text:
            return
        source = str(readme_path.relative_to(root))
        file_hash = None
        meta = meta_lookup.get("README.md")
        if meta:
            file_hash = meta.hash
        else:
            file_hash = _hash_text(text)
        visited_paths.add(source)
        if store.has_path_with_hash(source, file_hash):
            return
        store.remove_path(source)
        self._add_chunks(store, text, source=source, tags=["readme"], file_hash=file_hash)

    def _index_docs(
        self,
        files: Iterable[FileMeta],
        root: Path,
        store: EmbeddingStore,
        visited_paths: Set[str],
    ) -> None:
        for meta in files:
            if meta.role not in {"docs", "examples"} and not meta.path.startswith("docs/"):
                continue
            path = root / meta.path
            text = _read_text(path)
            if not text:
                continue
            tags = ["docs"]
            if meta.path.lower().startswith("docs/troubleshooting"):
                tags.append("troubleshooting")
            if meta.path.lower().startswith("docs/faq"):
                tags.append("faq")
            visited_paths.add(meta.path)
            if store.has_path_with_hash(meta.path, meta.hash):
                continue
            store.remove_path(meta.path)
            self._add_chunks(store, text, source=meta.path, tags=tags, file_hash=meta.hash)

    def _index_source_files(
        self,
        files: Iterable[FileMeta],
        root: Path,
        store: EmbeddingStore,
        visited_paths: Set[str],
    ) -> None:
        source_files = [meta for meta in files if meta.role == "src" and meta.language]
        source_files.sort(key=lambda meta: meta.size, reverse=True)
        for meta in source_files[: self.top_source_files]:
            path = root / meta.path
            text = _read_source_head(path)
            if not text:
                continue
            tags = ["source"]
            if meta.language:
                tags.append(meta.language.lower())
            visited_paths.add(meta.path)
            if store.has_path_with_hash(meta.path, meta.hash):
                continue
            store.remove_path(meta.path)
            self._add_chunks(store, text, source=meta.path, tags=tags, file_hash=meta.hash)

    def _add_chunks(
        self,
        store: EmbeddingStore,
        text: str,
        *,
        source: str,
        tags: Sequence[str],
        file_hash: str | None,
    ) -> None:
        chunks = self.embedder.chunk(text)
        for index, chunk in enumerate(chunks):
            vector = self.embedder.embed(chunk)
            sections = self._sections_for_tags(tags)
            chunk_id = f"{source}#{index}"
            metadata = {
                "path": source,
                "tags": list(tags),
                "hash": file_hash,
            }
            store.add(sections, chunk_id=chunk_id, vector=vector, text=chunk, metadata=metadata)

    @staticmethod
    def _sections_for_tags(tags: Sequence[str]) -> List[str]:
        sections: List[str] = []
        for tag in tags:
            sections.extend(TAG_SECTIONS.get(tag, []))
        return list(dict.fromkeys(sections))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _read_source_head(path: Path, *, max_chars: int = 2000) -> str:
    text = _read_text(path)
    if not text:
        return ""
    return text[:max_chars]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
