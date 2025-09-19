"""Embedding store for retrieval augmented generation."""


class EmbeddingStore:
    """Persists and retrieves embeddings scoped by README sections."""

    def add(self, key, vector):
        raise NotImplementedError

    def query(self, key, top_k: int = 5):
        raise NotImplementedError
