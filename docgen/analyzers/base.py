"""Base classes for analyzer plugins."""

from abc import ABC, abstractmethod
from typing import Iterable

from ..models import RepoManifest, Signal


class Analyzer(ABC):
    """Contract for analyzers that emit signals from the repo manifest."""

    @abstractmethod
    def supports(self, manifest: RepoManifest) -> bool:
        """Return True when this analyzer should run for the repository."""

    @abstractmethod
    def analyze(self, manifest: RepoManifest) -> Iterable[Signal]:
        """Produce structured signals used by prompting and post-processing."""
