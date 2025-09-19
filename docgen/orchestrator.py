"""Pipeline orchestration for init/update/regenerate flows."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

from .analyzers.base import Analyzer
from .analyzers.build import BuildAnalyzer
from .analyzers.dependencies import DependencyAnalyzer
from .analyzers.language import LanguageAnalyzer
from .models import Signal
from .prompting.builder import PromptBuilder
from .repo_scanner import RepoScanner


class Orchestrator:
    """Coordinates doc generation pipelines as described in the spec."""

    def __init__(
        self,
        scanner: RepoScanner | None = None,
        analyzers: Optional[Iterable[Analyzer]] = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self.scanner = scanner or RepoScanner()
        if analyzers is None:
            self.analyzers: List[Analyzer] = [
                LanguageAnalyzer(),
                BuildAnalyzer(),
                DependencyAnalyzer(),
            ]
        else:
            self.analyzers = list(analyzers)
        self.prompt_builder = prompt_builder or PromptBuilder()

    def run_init(self, path: str) -> Path:
        """Initialize README generation for a repository."""
        manifest = self.scanner.scan(path)

        signals: List[Signal] = []
        for analyzer in self.analyzers:
            if analyzer.supports(manifest):
                signals.extend(analyzer.analyze(manifest))

        readme_content = self.prompt_builder.build(manifest, signals)
        readme_path = Path(manifest.root) / "README.md"
        if readme_path.exists():
            raise FileExistsError(
                f"README already exists at {readme_path}. Use `docgen update` to refresh sections."
            )
        readme_path.write_text(readme_content, encoding="utf-8")
        return readme_path

    def run_update(self, path: str, diff_base: str) -> None:
        """Update README content after repository changes."""
        raise NotImplementedError

    def run_regenerate(
        self,
        path: str,
        sections: Optional[Iterable[str]] = None,
    ) -> None:
        """Regenerate README sections on demand."""
        raise NotImplementedError

