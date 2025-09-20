"""Embedding store for retrieval augmented generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


class EmbeddingStore:
    """Persists and retrieves embeddings scoped by README sections."""

    def __init__(self, path: Path | None = None, *, load_existing: bool = True) -> None:
        self._path = path
        self._store: Dict[str, List[Dict[str, object]]] = {}
        if path is not None and load_existing:
            self._load(path)

    def clear(self) -> None:
        """Remove all stored embeddings from memory."""
        self._store.clear()

    def add(
        self,
        sections: Sequence[str],
        *,
        chunk_id: str,
        vector: Dict[str, float],
        text: str,
        metadata: Dict[str, object],
    ) -> None:
        if not sections or not vector or not text.strip():
            return
        entry = {
            "id": chunk_id,
            "vector": vector,
            "text": text,
            "metadata": metadata,
        }
        for section in sections:
            self._store.setdefault(section, []).append(entry)

    def query(self, section: str, top_k: int = 5) -> List[Dict[str, object]]:
        entries = self._store.get(section, [])
        return entries[:top_k]

    def remove_path(self, path: str) -> None:
        normalized = path.replace("\\", "/")
        for entries in self._store.values():
            entries[:] = [entry for entry in entries if entry.get("metadata", {}).get("path") != normalized]

    def paths(self) -> Iterable[str]:
        seen: set[str] = set()
        for entries in self._store.values():
            for entry in entries:
                metadata = entry.get("metadata", {})
                path = metadata.get("path")
                if isinstance(path, str):
                    seen.add(path)
        return seen

    def has_path_with_hash(self, path: str, file_hash: str | None) -> bool:
        if not file_hash:
            return False
        normalized = path.replace("\\", "/")
        for entries in self._store.values():
            for entry in entries:
                metadata = entry.get("metadata", {})
                if metadata.get("path") == normalized and metadata.get("hash") == file_hash:
                    return True
        return False

    def persist(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        serialisable = {
            section: [self._prepare_entry(entry) for entry in entries]
            for section, entries in self._store.items()
        }
        self._path.write_text(json.dumps(serialisable, indent=2), encoding="utf-8")

    def _load(self, path: Path) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        for section, entries in data.items():
            if not isinstance(entries, list):
                continue
            valid_entries = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if "text" not in entry or "vector" not in entry:
                    continue
                valid_entries.append(entry)
            if valid_entries:
                self._store[section] = valid_entries

    @staticmethod
    def _prepare_entry(entry: Dict[str, object]) -> Dict[str, object]:
        vector = entry.get("vector", {})
        if isinstance(vector, dict):
            vector = {str(key): float(value) for key, value in vector.items() if isinstance(value, (int, float))}
        prepared = dict(entry)
        prepared["vector"] = vector
        return prepared

    def sections(self) -> Iterable[str]:
        return self._store.keys()
