"""Lightweight local embedder used for RAG-lite indexing."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, List


_WORD_PATTERN = re.compile(r"[A-Za-z0-9_]+")


class LocalEmbedder:
    """Handles simple chunking and bag-of-words embeddings."""

    def __init__(self, *, chunk_size: int = 350, overlap: int = 60) -> None:
        self.chunk_size = max(50, chunk_size)
        self.overlap = min(overlap, self.chunk_size // 2)

    def chunk(self, text: str) -> List[str]:
        words = text.split()
        if not words:
            return []
        chunk_len = self.chunk_size
        overlap = self.overlap
        chunks: List[str] = []
        start = 0
        while start < len(words):
            end = min(len(words), start + chunk_len)
            chunk = " ".join(words[start:end]).strip()
            if chunk:
                chunks.append(chunk)
            if end == len(words):
                break
            start = end - overlap
            if start < 0:
                start = 0
        return chunks

    def embed(self, text: str) -> dict[str, float]:
        tokens = [token.lower() for token in _WORD_PATTERN.findall(text)]
        if not tokens:
            return {}
        counts = Counter(tokens)
        norm = math.sqrt(sum(value * value for value in counts.values())) or 1.0
        return {token: value / norm for token, value in counts.items()}

    def embed_many(self, texts: Iterable[str]) -> List[dict[str, float]]:
        return [self.embed(text) for text in texts]
