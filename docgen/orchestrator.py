"""Pipeline orchestration for init/update/regenerate flows."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from .analyzers import Analyzer, discover_analyzers
from .config import ConfigError, DocGenConfig, load_config
from .git.diff import DiffAnalyzer, DiffResult
from .git.publisher import Publisher
from .models import Signal
from .postproc.lint import MarkdownLinter
from .postproc.markers import MarkerManager
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
        diff_analyzer: DiffAnalyzer | None = None,
        marker_manager: MarkerManager | None = None,
    ) -> None:
        self.scanner = scanner or RepoScanner()
        self._analyzer_overrides = list(analyzers) if analyzers is not None else None
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.publisher = publisher
        self.linter = linter
        self.toc_builder = toc_builder
        self.diff_analyzer = diff_analyzer or DiffAnalyzer()
        self.marker_manager = marker_manager or MarkerManager()

    def run_init(self, path: str) -> Path:
        """Initialize README generation for a repository."""
        repo_path = Path(path).expanduser().resolve()
        manifest = self.scanner.scan(str(repo_path))

        config = self._load_config(repo_path)
        analyzers = self._select_analyzers(config)

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

    def run_update(self, path: str, diff_base: str) -> Path | None:
        """Update README content after repository changes."""
        repo_path = Path(path).expanduser().resolve()
        readme_path = repo_path / "README.md"
        if not readme_path.exists():
            raise FileNotFoundError("README.md not found. Run `docgen init` first.")

        diff = self.diff_analyzer.compute(str(repo_path), diff_base)
        if not diff.sections:
            return None

        manifest = self.scanner.scan(str(repo_path))
        config = self._load_config(repo_path)
        analyzers = self._select_analyzers(config)

        signals: List[Signal] = []
        for analyzer in analyzers:
            if analyzer.supports(manifest):
                signals.extend(analyzer.analyze(manifest))

        builder = self.prompt_builder
        if config.templates_dir is not None:
            builder = PromptBuilder(config.templates_dir)

        new_sections = builder.render_sections(manifest, signals, diff.sections)
        if not new_sections:
            return None

        original = readme_path.read_text(encoding="utf-8")
        updated = original
        for section_name in diff.sections:
            section = new_sections.get(section_name)
            if section is None:
                continue
            updated = self.marker_manager.replace(updated, section_name, section.body)

        if updated == original:
            return None

        linted = self._lint(updated)
        final_content = self._apply_toc(linted)
        if final_content == original:
            return None

        readme_path.write_text(final_content, encoding="utf-8")
        self._publish_update(repo_path, readme_path, diff, config)
        return readme_path

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

    def _select_analyzers(self, config: DocGenConfig) -> List[Analyzer]:
        enabled = config.analyzers.enabled or None
        if self._analyzer_overrides is not None:
            return list(self._analyzer_overrides)
        return list(discover_analyzers(enabled))

    def _publish_update(
        self,
        repo_path: Path,
        readme_path: Path,
        diff: DiffResult,
        config: DocGenConfig,
    ) -> None:
        publisher = self.publisher or Publisher()
        publish_cfg = config.publish
        mode = publish_cfg.mode if publish_cfg and publish_cfg.mode else "pr"
        if mode == "commit":
            publisher.commit(
                str(repo_path),
                [readme_path],
                message="docs: update README via docgen",
            )
            return

        branch_prefix = publish_cfg.branch_prefix if publish_cfg and publish_cfg.branch_prefix else "docgen/readme-update"
        branch_name = self._build_branch_name(branch_prefix)
        title = self._build_pr_title(diff)
        body = self._build_pr_body(diff)
        publisher.publish_pr(
            str(repo_path),
            [readme_path],
            branch_name=branch_name,
            base_branch=diff.base,
            title=title,
            body=body,
        )

    @staticmethod
    def _build_branch_name(prefix: str) -> str:
        sanitized = prefix.strip().replace(" ", "-") or "docgen/readme-update"
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        if sanitized.endswith("/"):
            return f"{sanitized}{timestamp}"
        return f"{sanitized}-{timestamp}"

    @staticmethod
    def _build_pr_title(diff: DiffResult) -> str:
        if diff.sections:
            preview = ", ".join(diff.sections[:3])
            if len(diff.sections) > 3:
                preview += ", …"
            return f"docs: update README ({preview})"
        return "docs: update README via docgen"

    @staticmethod
    def _build_pr_body(diff: DiffResult) -> str:
        sections_line = ", ".join(diff.sections) if diff.sections else "(none)"
        changed_files = diff.changed_files or ["README.md"]
        lines = [
            "## Summary",
            f"- Updated sections: {sections_line}",
            f"- Diff base: `{diff.base}`",
            "",
            "## Changed files",
        ]
        lines.extend(f"- `{path}`" for path in changed_files)
        lines.extend([
            "",
            "Generated by `docgen update`.",
        ])
        return "\n".join(lines)
