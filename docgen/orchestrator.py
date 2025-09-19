"""Pipeline orchestration for init/update/regenerate flows."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

from .analyzers import Analyzer, discover_analyzers
from .config import ConfigError, DocGenConfig, load_config
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
        self._analyzer_overrides = list(analyzers) if analyzers is not None else None
        self.prompt_builder = prompt_builder or PromptBuilder()

    def run_init(self, path: str) -> Path:
        """Initialize README generation for a repository."""
        repo_path = Path(path).expanduser().resolve()
        manifest = self.scanner.scan(str(repo_path))

        config = self._load_config(repo_path)
        enabled_names = config.analyzers.enabled or None
        analyzers = self._analyzer_overrides or discover_analyzers(enabled_names)

        signals: List[Signal] = []
        for analyzer in analyzers:
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

    @staticmethod
    def _load_config(repo_path: Path) -> DocGenConfig:
        try:
            return load_config(repo_path)
        except ConfigError:
            return DocGenConfig(root=repo_path)
