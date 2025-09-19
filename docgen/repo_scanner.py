"""Repository scanning and manifest building utilities."""

from .models import RepoManifest


class RepoScanner:
    """Walks the repository to produce a normalized manifest."""

    def scan(self, root: str) -> RepoManifest:
        """Return a manifest describing project files and roles."""
        raise NotImplementedError
