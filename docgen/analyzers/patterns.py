"""Pattern analyzer stubs."""

from .base import Analyzer
from ..models import RepoManifest, Signal


class PatternAnalyzer(Analyzer):
    """Finds infrastructure and layout patterns within the repo."""

    def supports(self, manifest: RepoManifest) -> bool:
        raise NotImplementedError

    def analyze(self, manifest: RepoManifest):
        raise NotImplementedError
