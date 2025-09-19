"""Language-specific analyzer stubs."""

from .base import Analyzer
from ..models import RepoManifest, Signal


class LanguageAnalyzer(Analyzer):
    """Detects frameworks and idioms for supported languages."""

    def supports(self, manifest: RepoManifest) -> bool:
        raise NotImplementedError

    def analyze(self, manifest: RepoManifest):
        raise NotImplementedError
