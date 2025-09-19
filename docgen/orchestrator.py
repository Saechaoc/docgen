"""Pipeline orchestration for init/update/regenerate flows."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

from .analyzers import Analyzer, discover_analyzers
from .config import ConfigError, DocGenConfig, load_config
from .git.publisher import Publisher
from .models import Signal
from .postproc.lint import MarkdownLinter
from .postproc.toc import TableOfContentsBuilder
from .prompting.builder import PromptBuilder
from .repo_scanner import RepoScanner


class Orchestrator:
    """Coordinates doc generation pipelines as described in the spec."""

    def __init__(
        self,
        scanner: RepoScanner | None = None,
        analyzers: Optional[Iterable[Analyzer]] = None,
        prompt_builder: PromptBuilder | None = None,
        publisher: Publisher | None = None,
        linter: MarkdownLinter | None = None,
        toc_builder: TableOfContentsBuilder | None = None,
    ) -> None:
        self.scanner = scanner or RepoScanner()
        self._analyzer_overrides = list(analyzers) if analyzers is not None else None
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.publisher = publisher
        self.linter = linter
        self.toc_builder = toc_builder

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

        builder = self.prompt_builder
        if config.templates_dir is not None:
            builder = PromptBuilder(config.templates_dir)

        readme_content = builder.build(manifest, signals)
        linted = self._lint(readme_content)
        final_content = self._apply_toc(linted)

        readme_path = Path(manifest.root) / "README.md"
        if readme_path.exists():
            raise FileExistsError(
                f"README already exists at {readme_path}. Use `docgen update` to refresh sections."
            )
        readme_path.write_text(final_content, encoding="utf-8")

        self._maybe_commit(repo_path, readme_path, config)
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

    def _lint(self, markdown: str) -> str:
        linter = self.linter or MarkdownLinter()
        return linter.lint(markdown)

    def _apply_toc(self, markdown: str) -> str:
        toc_builder = self.toc_builder or TableOfContentsBuilder()
        return toc_builder.build(markdown)

    def _maybe_commit(self, repo_path: Path, readme_path: Path, config: DocGenConfig) -> None:
        publish_mode = config.publish.mode if config.publish else None
        if publish_mode != "commit":
            return
        publisher = self.publisher or Publisher()
        publisher.commit(str(repo_path), [readme_path], message="docs: bootstrap README via docgen init")

    @staticmethod
    def _load_config(repo_path: Path) -> DocGenConfig:
        try:
            return load_config(repo_path)
        except ConfigError:
            return DocGenConfig(root=repo_path)
