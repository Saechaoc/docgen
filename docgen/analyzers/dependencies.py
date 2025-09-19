"""Dependency analyzer stubs."""

from .base import Analyzer
from ..models import RepoManifest, Signal


class DependencyAnalyzer(Analyzer):
    """Collects dependency insights from manifest files."""

    def supports(self, manifest: RepoManifest) -> bool:
        raise NotImplementedError

    def analyze(self, manifest: RepoManifest):
        raise NotImplementedError
