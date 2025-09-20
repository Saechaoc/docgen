"""Pipeline orchestration for init/update/regenerate flows."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .analyzers import Analyzer, discover_analyzers
from .config import ConfigError, DocGenConfig, load_config
from .failsafe import build_readme_stub, build_section_stubs
from .git.diff import DiffAnalyzer, DiffResult, _pattern_matches as diff_pattern_matches
from .git.publisher import Publisher
from .logging import get_logger
from .models import RepoManifest, Signal
from .postproc.lint import MarkdownLinter
from .postproc.markers import MarkerManager
from .postproc.toc import TableOfContentsBuilder
from .prompting.builder import PromptBuilder
from .rag.indexer import RAGIndexer
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
        rag_indexer: RAGIndexer | None = None,
        diff_analyzer: DiffAnalyzer | None = None,
        marker_manager: MarkerManager | None = None,
    ) -> None:
        self.scanner = scanner or RepoScanner()
        self._analyzer_overrides = list(analyzers) if analyzers is not None else None
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.publisher = publisher
        self.linter = linter
        self.toc_builder = toc_builder
        self.rag_indexer = rag_indexer or RAGIndexer()
        self.diff_analyzer = diff_analyzer or DiffAnalyzer()
        self.marker_manager = marker_manager or MarkerManager()
        self.logger = get_logger("orchestrator")

    def run_init(self, path: str) -> Path:
        """Initialize README generation for a repository."""
        repo_path = Path(path).expanduser().resolve()
        self.logger.info("Starting init run for %s", repo_path)
        manifest = self.scanner.scan(str(repo_path))
        self.logger.debug("Scanner discovered %d files", len(manifest.files))

        config = self._load_config(repo_path)
        analyzers = self._select_analyzers(config)
        self.logger.debug("Selected %d analyzers", len(analyzers))

        signals: List[Signal] = []
        for analyzer in analyzers:
            if analyzer.supports(manifest):
                self.logger.debug("Running analyzer %s", analyzer.__class__.__name__)
                signals.extend(analyzer.analyze(manifest))

        builder = self._resolve_prompt_builder(config)

        contexts = self._build_contexts(manifest, sections=None)

        try:
            readme_content = builder.build(manifest, signals, contexts=contexts)
        except Exception as exc:  # pragma: no cover - defensive guard
            self._log_exception("Prompt builder failed during init", exc)
            readme_content = build_readme_stub(repo_path, reason=str(exc))
        if not readme_content.strip():
            self.logger.warning("Prompt builder produced empty README; using stub content")
            readme_content = build_readme_stub(repo_path)
        linted = self._lint(readme_content)
        final_content = self._apply_toc(linted)

        readme_path = Path(manifest.root) / "README.md"
        if readme_path.exists():
            raise FileExistsError(
                f"README already exists at {readme_path}. Use `docgen update` to refresh sections."
            )
        readme_path.write_text(final_content, encoding="utf-8")
        self.logger.info("README created at %s", readme_path)

        self._maybe_commit(repo_path, readme_path, config)
        return readme_path

    def run_update(self, path: str, diff_base: str) -> Path | None:
        """Update README content after repository changes."""
        repo_path = Path(path).expanduser().resolve()
        readme_path = repo_path / "README.md"
        if not readme_path.exists():
            raise FileNotFoundError("README.md not found. Run `docgen init` first.")

        self.logger.info("Starting update run for %s (base=%s)", repo_path, diff_base)
        diff = self.diff_analyzer.compute(str(repo_path), diff_base)
        if not diff.sections:
            self.logger.info("No README sections impacted by diff; skipping update")
            return None
        self.logger.debug("Update targets sections: %s", ", ".join(diff.sections))

        config = self._load_config(repo_path)
        if config.ci.watched_globs and not self._has_watched_changes(
            diff.changed_files,
            config.ci.watched_globs,
        ):
            self.logger.info(
                "Skipping README update because no changes matched watched_globs",
            )
            return None

        manifest = self.scanner.scan(str(repo_path))
        self.logger.debug("Scanner discovered %d files", len(manifest.files))
        analyzers = self._select_analyzers(config)
        self.logger.debug("Selected %d analyzers", len(analyzers))

        signals: List[Signal] = []
        for analyzer in analyzers:
            if analyzer.supports(manifest):
                self.logger.debug("Running analyzer %s", analyzer.__class__.__name__)
                signals.extend(analyzer.analyze(manifest))

        builder = self._resolve_prompt_builder(config)

        contexts = self._build_contexts(manifest, sections=diff.sections)

        try:
            new_sections = builder.render_sections(
                manifest,
                signals,
                diff.sections,
                contexts=contexts,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            self._log_exception("Prompt builder failed during update", exc)
            project_name = repo_path.name or "Repository"
            new_sections = build_section_stubs(diff.sections, project_name=project_name, reason=str(exc))
        if not new_sections:
            self.logger.warning("Prompt builder returned no sections for update; using stub content")
            project_name = repo_path.name or "Repository"
            new_sections = build_section_stubs(diff.sections, project_name=project_name)
            if not new_sections:
                return None
        else:
            missing = [
                name
                for name in diff.sections
                if not (new_sections.get(name).body.strip() if new_sections.get(name) else "")
            ]
            if missing:
                self.logger.warning(
                    "Prompt builder produced empty sections (%s); using stub content",
                    ", ".join(missing),
                )
                project_name = repo_path.name or "Repository"
                stub_sections = build_section_stubs(missing, project_name=project_name)
                new_sections.update(stub_sections)

        original = readme_path.read_text(encoding="utf-8")
        updated = original
        for section_name in diff.sections:
            section = new_sections.get(section_name)
            if section is None:
                continue
            updated = self.marker_manager.replace(updated, section_name, section.body)

        if updated == original:
            self.logger.info("Rendered sections are identical to existing content; skipping write")
            return None

        linted = self._lint(updated)
        final_content = self._apply_toc(linted)
        if final_content == original:
            self.logger.info("Post-processed README identical to existing version; skipping write")
            return None

        readme_path.write_text(final_content, encoding="utf-8")
        self.logger.info("README updated at %s", readme_path)
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
        self.logger.info("Committing README via publisher")
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

    def _build_contexts(
        self,
        manifest: RepoManifest,
        *,
        sections: Iterable[str] | None,
    ) -> Dict[str, List[str]]:
        try:
            index = self.rag_indexer.build(manifest, sections=list(sections) if sections else None)
        except Exception as exc:
            target = ", ".join(sections) if sections else "all sections"
            self.logger.warning("RAG index build failed for %s: %s", target, exc)
            return {}
        return index.contexts

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
            self.logger.info("Publishing README update via commit")
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
        self.logger.info("Publishing README update via PR on branch %s", branch_name)
        publisher.publish_pr(
            str(repo_path),
            [readme_path],
            branch_name=branch_name,
            base_branch=diff.base,
            title=title,
            body=body,
        )

    def _log_exception(self, message: str, exc: Exception) -> None:
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.exception("%s: %s", message, exc)
        else:
            self.logger.error("%s: %s", message, exc)

    def _resolve_prompt_builder(self, config: DocGenConfig) -> PromptBuilder:
        base = self.prompt_builder
        style = config.readme_style or getattr(base, "style", "comprehensive")
        templates_dir = config.templates_dir
        if templates_dir is None and config.readme_style is None:
            return base
        if templates_dir is not None:
            self.logger.debug("Using custom templates from %s", templates_dir)
        return PromptBuilder(templates_dir, style=style)

    @staticmethod
    def _has_watched_changes(paths: Sequence[str], globs: Sequence[str]) -> bool:
        if not globs:
            return True
        normalised_patterns = [pattern.replace("\\", "/") for pattern in globs]
        for raw_path in paths:
            path = raw_path.replace("\\", "/")
            for pattern in normalised_patterns:
                if Orchestrator._match_pattern(path, pattern):
                    return True
        return False

    @staticmethod
    def _match_pattern(path: str, pattern: str) -> bool:
        normalized = path.replace("\\", "/")
        if diff_pattern_matches(normalized, pattern):
            return True
        if pattern.startswith("**/"):
            return diff_pattern_matches(normalized, pattern[3:])
        return False

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
