"""Build system analyzer stubs."""

from .base import Analyzer
from ..models import RepoManifest, Signal


class BuildAnalyzer(Analyzer):
    """Captures build tooling and workflows from manifests."""

    def supports(self, manifest: RepoManifest) -> bool:
        raise NotImplementedError

    def analyze(self, manifest: RepoManifest):
        raise NotImplementedError
