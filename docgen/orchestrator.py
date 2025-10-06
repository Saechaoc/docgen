"""Pipeline orchestration for init/update/regenerate flows."""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
import difflib
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, cast

from .analyzers import Analyzer, discover_analyzers
from .config import ConfigError, DocGenConfig, LLMConfig, load_config
from .failsafe import build_readme_stub, build_section_stubs
from .git.diff import DiffAnalyzer, DiffResult, _pattern_matches as diff_pattern_matches
from .git.publisher import Publisher
from .logging import get_logger
from .models import RepoManifest, Signal
from .postproc.lint import MarkdownLinter
from .postproc.markers import MarkerManager
from .postproc.toc import TableOfContentsBuilder
from .postproc.badges import BadgeManager
from .postproc.links import LinkValidator
from .postproc.scorecard import ReadmeScorecard
from .llm.runner import LLMRunner
from .prompting.builder import PromptBuilder, Section
from .prompting.constants import DEFAULT_SECTIONS, SECTION_TITLES
from .rag.indexer import RAGIndexer
from .repo_scanner import RepoScanner
from .stores import AnalyzerCache
from .validators import (
    NoHallucinationValidator,
    ValidationContext,
    ValidationError,
    ValidationIssue,
    Validator,
    build_evidence_index,
)


@dataclass
class UpdateOutcome:
    """Result of a README update operation."""

    path: Path
    diff: str
    dry_run: bool


@dataclass
class ValidationSettings:
    """Effective validation configuration for a pipeline run."""

    enabled: bool
    mode: str
    allow_inferred: bool
    source: str


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
        badge_manager: BadgeManager | None = None,
        link_validator: LinkValidator | None = None,
        scorecard: ReadmeScorecard | None = None,
        llm_runner: LLMRunner | None = None,
        validators: Optional[Iterable[Validator]] = None,
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
        self.badge_manager = badge_manager or BadgeManager()
        self.link_validator = link_validator or LinkValidator()
        self.scorecard = scorecard or ReadmeScorecard()
        self.logger = get_logger("orchestrator")
        self._llm_runner = llm_runner
        self._llm_runner_is_external = llm_runner is not None
        self._llm_runner_signature: tuple[object | None, ...] | None = None
        self._validator_overrides = list(validators) if validators is not None else None
        self._validator_cache: Dict[Tuple[str, bool], List[Validator]] = {}
        self._rag_refresh_thread: Optional[threading.Thread] = None

    def run_init(self, path: str, *, skip_validation: bool = False) -> Path:
        """Initialize README generation for a repository."""
        repo_path = Path(path).expanduser().resolve()
        self.logger.info("Starting init run for %s", repo_path)
        manifest = self.scanner.scan(str(repo_path))
        self.logger.debug("Scanner discovered %d files", len(manifest.files))

        config = self._load_config(repo_path)
        analyzers = self._select_analyzers(config)
        self.logger.debug("Selected %d analyzers", len(analyzers))

        cache = self._load_analyzer_cache(repo_path)
        signals = self._execute_analyzers(manifest, analyzers, cache)

        builder = self._resolve_prompt_builder(config, repo_path)

        contexts = self._build_contexts(manifest, sections=None)
        token_budgets = self._build_token_budget_map(config)
        runner = self._resolve_llm_runner(config)

        section_order = list(DEFAULT_SECTIONS)
        project_name = repo_path.name or "Repository"
        sections_map: Dict[str, Section] = {}
        builder_failed = False
        allowed_llm_sections = self._llm_sections_for_config(config, section_order)

        try:
            fallback_sections = builder.render_sections(
                manifest,
                signals,
                section_order,
                contexts=contexts,
                token_budgets=token_budgets,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            builder_failed = True
            self._log_exception("Prompt builder failed during init", exc)
            fallback_sections = build_section_stubs(section_order, project_name=project_name, reason=str(exc))
            sections_map = self._clone_sections(fallback_sections)
        else:
            try:
                can_stream = runner is not None and hasattr(builder, "build_prompt_requests")
                if can_stream:
                    sections_map = self._generate_sections_with_llm(
                        cast(PromptBuilder, builder),
                        runner,
                        manifest,
                        signals,
                        section_order,
                        contexts,
                        token_budgets,
                        fallback_sections,
                        allowed_llm_sections,
                    )
                else:
                    if runner and not can_stream:
                        self.logger.debug(
                            "LLM runner enabled but prompt builder %s lacks build_prompt_requests; falling back to template rendering",
                            builder.__class__.__name__,
                        )
                    sections_map = self._clone_sections(fallback_sections)
            except Exception as exc:  # pragma: no cover - defensive guard
                builder_failed = True
                self._log_exception("Prompt builder failed during init", exc)
                fallback_sections = build_section_stubs(section_order, project_name=project_name, reason=str(exc))
                sections_map = self._clone_sections(fallback_sections)

        if not sections_map:
            self.logger.warning("Prompt builder returned no sections; using stub content")
            sections_map = build_section_stubs(section_order, project_name=project_name)
        else:
            sections_map = self._fill_missing_sections(
                sections_map,
                required=section_order,
                project_name=project_name,
            )

        effective_skip = skip_validation or builder_failed
        skip_label = "flag" if skip_validation else None
        if builder_failed and not skip_validation:
            skip_label = "fallback"

        validation_retried = False
        while True:
            try:
                validated_sections = self._run_validators_if_enabled(
                    repo_path,
                    manifest,
                    signals,
                    sections_map,
                    config,
                    skip_validation=effective_skip,
                    request_sections=section_order,
                    skip_reason=skip_label,
                )
                break
            except ValidationError as exc:
                if validation_retried:
                    raise
                if not self._apply_validation_fallback(exc, sections_map, fallback_sections):
                    raise
                self.logger.warning(
                    "Validation failed for %s; falling back to deterministic templates before retry",
                    ", ".join(sorted({issue.section for issue in exc.issues})),
                )
                effective_skip = False
                skip_label = None
                validation_retried = True

        readme_content = self._render_readme_from_sections(
            builder,
            manifest,
            validated_sections,
            section_order,
        )
        if not readme_content.strip():
            self.logger.warning("Prompt builder produced empty README; using stub content")
            readme_content = build_readme_stub(repo_path)
        linted = self._lint(readme_content)
        final_content = self._apply_badges(self._apply_toc(linted))
        link_issues = self._validate_links(final_content, repo_path)
        self._record_scorecard(repo_path, final_content, link_issues)

        readme_path = Path(manifest.root) / "README.md"
        if readme_path.exists():
            raise FileExistsError(
                f"README already exists at {readme_path}. Use `docgen update` to refresh sections."
            )
        readme_path.write_text(final_content, encoding="utf-8")
        self.logger.info("README created at %s", readme_path)

        self._refresh_rag_index_async(manifest, section_order)

        self._maybe_commit(repo_path, readme_path, config)
        return readme_path

    def run_update(
        self,
        path: str,
        diff_base: str,
        *,
        dry_run: bool = False,
        skip_validation: bool = False,
    ) -> UpdateOutcome | None:
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

        cache = self._load_analyzer_cache(repo_path)
        signals = self._execute_analyzers(manifest, analyzers, cache)

        builder = self._resolve_prompt_builder(config, repo_path)

        contexts = self._build_contexts(manifest, sections=diff.sections)
        token_budgets = self._build_token_budget_map(config)
        runner = self._resolve_llm_runner(config)

        project_name = repo_path.name or "Repository"
        sections_map: Dict[str, Section] = {}
        builder_failed = False
        allowed_llm_sections = self._llm_sections_for_config(config, diff.sections)

        try:
            fallback_sections = builder.render_sections(
                manifest,
                signals,
                diff.sections,
                contexts=contexts,
                token_budgets=token_budgets,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            builder_failed = True
            self._log_exception("Prompt builder failed during update", exc)
            fallback_sections = build_section_stubs(diff.sections, project_name=project_name, reason=str(exc))
            sections_map = self._clone_sections(fallback_sections)
        else:
            try:
                can_stream = runner is not None and hasattr(builder, "build_prompt_requests")
                if can_stream:
                    sections_map = self._generate_sections_with_llm(
                        cast(PromptBuilder, builder),
                        runner,
                        manifest,
                        signals,
                        diff.sections,
                        contexts,
                        token_budgets,
                        fallback_sections,
                        allowed_llm_sections,
                    )
                else:
                    if runner and not can_stream:
                        self.logger.debug(
                            "LLM runner enabled but prompt builder %s lacks build_prompt_requests; using render_sections",
                            builder.__class__.__name__,
                        )
                    sections_map = self._clone_sections(fallback_sections)
            except Exception as exc:  # pragma: no cover - defensive guard
                builder_failed = True
                self._log_exception("Prompt builder failed during update", exc)
                fallback_sections = build_section_stubs(diff.sections, project_name=project_name, reason=str(exc))
                sections_map = self._clone_sections(fallback_sections)

        if not sections_map:
            self.logger.warning("Prompt builder returned no sections for update; using stub content")
            sections_map = build_section_stubs(diff.sections, project_name=project_name)
            if not sections_map:
                self._refresh_rag_index_async(manifest, list(DEFAULT_SECTIONS))
                return None
        else:
            sections_map = self._fill_missing_sections(
                sections_map,
                required=diff.sections,
                project_name=project_name,
            )

        effective_skip = skip_validation or builder_failed
        skip_label = "flag" if skip_validation else None
        if builder_failed and not skip_validation:
            skip_label = "fallback"

        validation_retried = False
        while True:
            try:
                validated_sections = self._run_validators_if_enabled(
                    repo_path,
                    manifest,
                    signals,
                    sections_map,
                    config,
                    skip_validation=effective_skip,
                    request_sections=diff.sections,
                    skip_reason=skip_label,
                )
                break
            except ValidationError as exc:
                if validation_retried:
                    raise
                if not self._apply_validation_fallback(exc, sections_map, fallback_sections):
                    raise
                self.logger.warning(
                    "Validation failed for %s; reverting to deterministic sections before retry",
                    ", ".join(sorted({issue.section for issue in exc.issues})),
                )
                effective_skip = False
                skip_label = None
                validation_retried = True

        original = readme_path.read_text(encoding="utf-8")
        updated = original
        for section_name in diff.sections:
            section = validated_sections.get(section_name)
            if section is None:
                continue
            updated = self.marker_manager.replace(updated, section_name, section.body)

        if updated == original:
            self.logger.info("Rendered sections are identical to existing content; skipping write")
            self._refresh_rag_index_async(manifest, list(DEFAULT_SECTIONS))
            return None

        linted = self._lint(updated)
        final_content = self._apply_badges(self._apply_toc(linted))
        if final_content == original:
            self.logger.info("Post-processed README identical to existing version; skipping write")
            self._refresh_rag_index_async(manifest, list(DEFAULT_SECTIONS))
            return None

        link_issues = self._validate_links(final_content, repo_path)
        diff_text = self._render_diff(original, final_content)

        if dry_run:
            self._record_scorecard(repo_path, final_content, link_issues, dry_run=True)
            self._refresh_rag_index_async(manifest, list(DEFAULT_SECTIONS))
            self.logger.info("Dry-run completed; README changes not written")
            return UpdateOutcome(path=readme_path, diff=diff_text, dry_run=True)

        readme_path.write_text(final_content, encoding="utf-8")
        self.logger.info("README updated at %s", readme_path)
        self._record_scorecard(repo_path, final_content, link_issues)
        self._publish_update(repo_path, readme_path, diff, config)
        self._refresh_rag_index_async(manifest, list(DEFAULT_SECTIONS))
        return UpdateOutcome(path=readme_path, diff=diff_text, dry_run=False)

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
        section_list = list(sections) if sections else None
        try:
            index = self.rag_indexer.load(manifest, sections=section_list)
        except Exception as exc:
            target = ", ".join(section_list or []) if section_list else "all sections"
            self.logger.debug("RAG context load failed for %s: %s", target, exc)
            return {}
        if index is None:
            return {}
        return index.contexts

    def _refresh_rag_index_async(
        self,
        manifest: RepoManifest,
        sections: Sequence[str] | None,
    ) -> None:
        if self._rag_refresh_thread and self._rag_refresh_thread.is_alive():
            return

        section_list = list(dict.fromkeys(sections)) if sections else None
        rag_indexer = self.rag_indexer

        def _worker() -> None:
            try:
                rag_indexer.build(manifest, sections=section_list)
            except Exception as exc:  # pragma: no cover - background best effort
                self.logger.debug("Async RAG rebuild failed: %s", exc)

        thread = threading.Thread(target=_worker, name="docgen-rag-refresh", daemon=True)
        self._rag_refresh_thread = thread
        thread.start()

    def _build_token_budget_map(self, config: DocGenConfig) -> Dict[str, int]:
        budgets: Dict[str, int] = {}
        if config.token_budget_default is not None:
            budgets["default"] = config.token_budget_default
        if config.token_budget_overrides:
            budgets.update(config.token_budget_overrides)
        return budgets

    def _load_analyzer_cache(self, repo_path: Path) -> AnalyzerCache:
        cache_path = repo_path / ".docgen" / "analyzers" / "cache.json"
        return AnalyzerCache(cache_path)

    def _execute_analyzers(
        self,
        manifest: RepoManifest,
        analyzers: Sequence[Analyzer],
        cache: AnalyzerCache,
    ) -> List[Signal]:
        fingerprint = self._manifest_fingerprint(manifest)
        signals: List[Signal] = []
        used_keys: List[str] = []
        for analyzer in analyzers:
            if not analyzer.supports(manifest):
                continue
            key = self._analyzer_cache_key(analyzer)
            signature = self._analyzer_signature(analyzer)
            used_keys.append(key)
            cached = cache.get(key, signature=signature, fingerprint=fingerprint)
            if cached is not None:
                self.logger.debug("Using cached analyzer results for %s", key)
                signals.extend(cached)
                continue
            self.logger.debug("Running analyzer %s", analyzer.__class__.__name__)
            computed = list(analyzer.analyze(manifest))
            cache.store(key, signature=signature, fingerprint=fingerprint, signals=computed)
            signals.extend(computed)
        cache.prune(used_keys)
        cache.persist()
        return signals

    @staticmethod
    def _analyzer_cache_key(analyzer: Analyzer) -> str:
        return f"{analyzer.__class__.__module__}.{analyzer.__class__.__qualname__}"

    @staticmethod
    def _analyzer_signature(analyzer: Analyzer) -> str:
        module = analyzer.__class__.__module__
        qualname = analyzer.__class__.__qualname__
        cache_version = (
            getattr(analyzer, "cache_version", None)
            or getattr(analyzer.__class__, "cache_version", None)
            or getattr(analyzer, "__cache_version__", None)
            or getattr(analyzer.__class__, "__cache_version__", None)
            or "1"
        )
        try:
            source = inspect.getsource(analyzer.__class__)
        except (OSError, TypeError):
            source_hash = f"{module}:{qualname}"
        else:
            source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return f"{module}.{qualname}:{cache_version}:{source_hash}"

    @staticmethod
    def _manifest_fingerprint(manifest: RepoManifest) -> str:
        entries = [
            (
                file.path.replace("\\", "/"),
                file.hash or "",
            )
            for file in manifest.files
            if Orchestrator._include_in_cache_fingerprint(file.path)
        ]
        entries.sort(key=lambda item: item[0])
        digest = hashlib.sha256()
        for path, file_hash in entries:
            digest.update(path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(file_hash.encode("utf-8"))
            digest.update(b"\0")
        digest.update(str(len(entries)).encode("utf-8"))
        return digest.hexdigest()

    @staticmethod
    def _include_in_cache_fingerprint(path: str) -> bool:
        normalized = path.replace("\\", "/").lower()
        if normalized == "readme.md":
            return False
        return True

    def _fill_missing_sections(
        self,
        sections: Dict[str, Section],
        *,
        required: Sequence[str],
        project_name: str,
        reason: str | None = None,
    ) -> Dict[str, Section]:
        missing = [
            name
            for name in required
            if name not in sections
            or not sections[name]
            or not sections[name].body.strip()
        ]
        if missing:
            self.logger.warning(
                "Prompt builder produced empty sections (%s); using stub content",
                ", ".join(missing),
            )
            stub_sections = build_section_stubs(missing, project_name=project_name, reason=reason)
            sections.update(stub_sections)
        return sections

    def _run_validators_if_enabled(
        self,
        repo_path: Path,
        manifest: RepoManifest,
        signals: Sequence[Signal],
        sections: Dict[str, Section],
        config: DocGenConfig,
        *,
        skip_validation: bool,
        request_sections: Sequence[str],
        skip_reason: Optional[str],
    ) -> Dict[str, Section]:
        settings = self._compute_validation_settings(config)
        issues: List[ValidationIssue] = []

        if skip_validation:
            reason = skip_reason or "override"
            self.logger.info("Skipping README validation for this run (%s).", reason)
            self._write_validation_report(
                repo_path,
                status="skipped",
                mode=settings.mode,
                mode_source=settings.source,
                allow_inferred=settings.allow_inferred,
                validators=[],
                issues=issues,
                sections=sections,
                request_sections=request_sections,
                skip_reason=reason,
            )
            return sections

        if not settings.enabled:
            reason = skip_reason or settings.source
            self.logger.info("README validation disabled via %s settings.", settings.source)
            self._write_validation_report(
                repo_path,
                status="disabled",
                mode=settings.mode,
                mode_source=settings.source,
                allow_inferred=settings.allow_inferred,
                validators=[],
                issues=issues,
                sections=sections,
                request_sections=request_sections,
                skip_reason=reason,
            )
            return sections

        validators = self._resolve_validators(settings)
        if not validators:
            self.logger.debug("No validators configured; skipping validation stage")
            self._write_validation_report(
                repo_path,
                status="disabled",
                mode=settings.mode,
                mode_source=settings.source,
                allow_inferred=settings.allow_inferred,
                validators=[],
                issues=issues,
                sections=sections,
                request_sections=request_sections,
                skip_reason="empty",
            )
            return sections

        evidence = build_evidence_index(signals, sections)
        context = ValidationContext(
            manifest=manifest,
            signals=signals,
            sections=sections,
            evidence=evidence,
        )

        for validator in validators:
            issues.extend(validator.validate(context))

        if issues:
            offending_sections = sorted({issue.section for issue in issues})
            for issue in issues:
                self.logger.error("Validation failure in section '%s': %s", issue.section, issue.detail)
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("Sentence: %s", issue.sentence)
            self._write_validation_report(
                repo_path,
                status="failed",
                mode=settings.mode,
                mode_source=settings.source,
                allow_inferred=settings.allow_inferred,
                validators=validators,
                issues=issues,
                sections=sections,
                request_sections=request_sections,
                skip_reason=None,
            )
            raise ValidationError(
                "README validation failed; rerun with --verbose for offending sentences",
                issues,
            )

        self.logger.debug("Validation passed for %d section(s)", len(sections))
        self._write_validation_report(
            repo_path,
            status="passed",
            mode=settings.mode,
            mode_source=settings.source,
            allow_inferred=settings.allow_inferred,
            validators=validators,
            issues=issues,
            sections=sections,
            request_sections=request_sections,
            skip_reason=None,
        )
        return sections

    def _compute_validation_settings(self, config: DocGenConfig) -> ValidationSettings:
        raw_mode = (config.validation.mode or "") if config.validation else ""
        normalized_mode = raw_mode.strip().lower()
        if normalized_mode in {"deterministic"}:
            normalized_mode = "strict"
        if normalized_mode not in {"balanced", "strict", "off"}:
            normalized_mode = "balanced"

        allow_inferred = config.validation.allow_inferred if config.validation else None
        if allow_inferred is None:
            allow_inferred = config.generation.allow_inferred
        if allow_inferred is None:
            allow_inferred = normalized_mode == "balanced"
        allow_inferred_bool = bool(allow_inferred)

        env_value = os.getenv("DOCGEN_VALIDATION_NO_HALLUCINATION")
        env_bool = self._parse_env_bool(env_value) if env_value is not None else None

        source = "config"
        enabled = getattr(config.validation, "no_hallucination", True)
        if normalized_mode == "off":
            enabled = False
        if env_bool is not None:
            enabled = env_bool
            source = "env"

        return ValidationSettings(
            enabled=bool(enabled),
            mode=normalized_mode,
            allow_inferred=allow_inferred_bool,
            source=source,
        )

    def _resolve_validators(self, settings: ValidationSettings) -> List[Validator]:
        if self._validator_overrides is not None:
            return list(self._validator_overrides)
        key = (settings.mode, settings.allow_inferred)
        cached = self._validator_cache.get(key)
        if cached is None:
            cached = [NoHallucinationValidator(mode=settings.mode, allow_inferred=settings.allow_inferred)]
            self._validator_cache[key] = cached
        return list(cached)

    @staticmethod
    def _parse_env_bool(value: Optional[str]) -> Optional[bool]:
        if value is None:
            return None
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        return None

    def _write_validation_report(
        self,
        repo_path: Path,
        *,
        status: str,
        mode: str,
        mode_source: str,
        allow_inferred: bool,
        validators: Sequence[Validator],
        issues: Sequence[ValidationIssue],
        sections: Mapping[str, Section],
        request_sections: Sequence[str],
        skip_reason: Optional[str],
    ) -> None:
        report_dir = repo_path / ".docgen"
        try:
            report_dir.mkdir(parents=True, exist_ok=True)
        except Exception:  # pragma: no cover - filesystem guard
            self.logger.debug("Unable to create validation report directory", exc_info=True)
            return
        report_path = report_dir / "validation.json"
        evidence_summary: Dict[str, Dict[str, int]] = {}
        for name, section in sections.items():
            metadata = section.metadata if isinstance(section.metadata, dict) else {}
            context_values = metadata.get("context") if isinstance(metadata, dict) else []
            if isinstance(context_values, Sequence) and not isinstance(context_values, (str, bytes)):
                context_count = len(context_values)
            else:
                context_count = 0
            evidence_meta = metadata.get("evidence") if isinstance(metadata, dict) else {}
            signal_count = 0
            if isinstance(evidence_meta, Mapping):
                signals_field = evidence_meta.get("signals")
                if isinstance(signals_field, Sequence) and not isinstance(signals_field, (str, bytes)):
                    signal_count = len(list(signals_field))
            evidence_summary[name] = {
                "context_chunks": context_count,
                "signal_count": signal_count,
            }
        now_utc = datetime.now(UTC)
        payload = {
            "status": status,
            "mode": mode,
            "mode_source": mode_source,
            "allow_inferred": allow_inferred,
            "skip_reason": skip_reason,
            "validators": [validator.name for validator in validators],
            "issue_count": len(issues),
            "issues": [
                {
                    "section": issue.section,
                    "sentence": issue.sentence,
                    "missing_terms": issue.missing_terms,
                    "detail": issue.detail,
                }
                for issue in issues
            ],
            "requested_sections": list(request_sections),
            "evidence_summary": evidence_summary,
            "generated_at": now_utc.isoformat().replace("+00:00", "Z"),
        }
        try:
            report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:  # pragma: no cover - filesystem guard
            self.logger.debug("Unable to write validation report", exc_info=True)

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
        labels = publish_cfg.labels if publish_cfg else []
        update_existing = publish_cfg.update_existing if publish_cfg else False
        publisher.publish_pr(
            str(repo_path),
            [readme_path],
            branch_name=branch_name,
            base_branch=diff.base,
            title=title,
            body=body,
            labels=labels,
            update_existing=update_existing,
        )

    def _log_exception(self, message: str, exc: Exception) -> None:
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.exception("%s: %s", message, exc)
        else:
            self.logger.error("%s: %s", message, exc)

    def _resolve_prompt_builder(self, config: DocGenConfig, repo_path: Path) -> PromptBuilder:
        base = self.prompt_builder
        if not isinstance(base, PromptBuilder):
            return base

        style = config.readme_style or getattr(base, "style", "comprehensive")
        templates_dir = config.templates_dir
        if templates_dir is None:
            candidate = repo_path / "docs" / "templates"
            if candidate.exists() and candidate.is_dir():
                templates_dir = candidate

        template_pack = config.template_pack or getattr(base, "template_pack", None)
        token_budget_default = (
            config.token_budget_default
            if config.token_budget_default is not None
            else getattr(base, "_token_budget_default", None)
        )
        token_budget_overrides = (
            config.token_budget_overrides
            if config.token_budget_overrides
            else getattr(base, "_token_budget_overrides", {})
        )

        if (
            style == getattr(base, "style", "comprehensive")
            and templates_dir is None
            and template_pack == getattr(base, "template_pack", None)
            and token_budget_default == getattr(base, "_token_budget_default", None)
            and token_budget_overrides == getattr(base, "_token_budget_overrides", {})
        ):
            return base

        if templates_dir is not None:
            self.logger.debug("Using custom templates from %s", templates_dir)

        return PromptBuilder(
            templates_dir,
            style=style,
            template_pack=template_pack,
            token_budget_default=token_budget_default,
            token_budget_overrides=token_budget_overrides,
        )

    def _resolve_llm_runner(self, config: DocGenConfig) -> LLMRunner | None:
        if self._llm_runner_is_external and self._llm_runner is not None:
            return self._llm_runner

        llm_cfg = config.llm
        if llm_cfg is None and not self._llm_runner_is_external:
            if not self._llm_environment_available():
                self.logger.debug("No LLM configuration detected; using deterministic generation mode.")
                self._llm_runner = None
                self._llm_runner_signature = None
                return None
            llm_cfg = LLMConfig()
        elif llm_cfg is None:
            llm_cfg = LLMConfig()

        signature = (
            llm_cfg.runner,
            llm_cfg.model,
            llm_cfg.executable,
            llm_cfg.base_url,
            llm_cfg.temperature,
            llm_cfg.max_tokens,
            llm_cfg.api_key,
            llm_cfg.request_timeout,
        )

        if self._llm_runner_signature == signature and self._llm_runner is not None:
            return self._llm_runner

        runner = None
        try:
            if llm_cfg.runner and llm_cfg.runner.lower() in {"llama.cpp", "llamacpp"}:
                if not llm_cfg.model:
                    self.logger.warning("llama.cpp runner requires `model` to be configured in .docgen.yml")
                    return None
                from .llm.llamacpp import LlamaCppRunner

                model_path = Path(llm_cfg.model).expanduser()
                if not model_path.is_absolute():
                    model_path = (config.root / model_path).resolve()
                runner = LlamaCppRunner(
                    model_path=str(model_path),
                    executable=llm_cfg.executable or llm_cfg.runner,
                    temperature=llm_cfg.temperature,
                    max_tokens=llm_cfg.max_tokens,
                )
            else:
                kwargs: Dict[str, object] = {}
                executable = llm_cfg.executable or llm_cfg.runner
                if executable:
                    kwargs["executable"] = executable
                if llm_cfg.model:
                    kwargs["model"] = llm_cfg.model
                if llm_cfg.base_url is not None:
                    kwargs["base_url"] = llm_cfg.base_url
                if llm_cfg.temperature is not None:
                    kwargs["temperature"] = llm_cfg.temperature
                if llm_cfg.max_tokens is not None:
                    kwargs["max_tokens"] = llm_cfg.max_tokens
                if llm_cfg.api_key is not None:
                    kwargs["api_key"] = llm_cfg.api_key
                if llm_cfg.request_timeout is not None:
                    kwargs["request_timeout"] = llm_cfg.request_timeout
                runner = LLMRunner(**kwargs)  # type: ignore[arg-type]
        except Exception as exc:  # pragma: no cover - defensive guard
            self.logger.warning("Failed to initialise LLM runner: %s", exc)
            return None
        self._llm_runner = runner
        self._llm_runner_signature = signature
        self._llm_runner_is_external = False
        return runner

    @staticmethod
    def _llm_environment_available() -> bool:
        from .llm.runner import LLMRunner

        env_keys = (
            list(LLMRunner.ENV_MODEL_KEYS)
            + list(LLMRunner.ENV_BASE_URL_KEYS)
            + list(LLMRunner.ENV_API_KEY_KEYS)
        )
        return any(os.getenv(key) for key in env_keys)

    @staticmethod
    def _canonical_section_name(name: str) -> str:
        cleaned = name.strip().lower()
        cleaned = cleaned.replace(" ", "_")
        cleaned = cleaned.replace("-", "_")
        return cleaned

    def _llm_sections_for_config(
        self,
        config: DocGenConfig,
        requested_sections: Sequence[str],
    ) -> Set[str]:
        canonical_requested: Dict[str, str] = {
            self._canonical_section_name(section): section for section in requested_sections
        }

        mode_raw = config.generation.mode if config.generation and config.generation.mode else "balanced"
        mode = mode_raw.strip().lower()
        if mode in {"strict", "deterministic"}:
            allowed_canonical: Set[str] = set()
        elif mode == "model-first":
            allowed_canonical = set(canonical_requested.keys())
        else:
            default_targets = {"intro", "architecture", "features", "deployment"}
            allowed_canonical = {
                self._canonical_section_name(name)
                for name in default_targets
                if self._canonical_section_name(name) in canonical_requested
            }

        overrides = config.generation.section_overrides if config.generation else {}
        for raw_name, flag in overrides.items():
            canonical = self._canonical_section_name(str(raw_name))
            if not flag:
                allowed_canonical.discard(canonical)
                continue
            if canonical in canonical_requested:
                allowed_canonical.add(canonical)

        allowed_sections: Set[str] = set()
        for canonical in allowed_canonical:
            original = canonical_requested.get(canonical)
            if original is not None:
                allowed_sections.add(original)
        return allowed_sections

    def _generate_sections_with_llm(
        self,
        builder: PromptBuilder,
        runner: LLMRunner,
        manifest: RepoManifest,
        signals: Iterable[Signal],
        section_names: Sequence[str],
        contexts: Dict[str, List[str]],
        token_budgets: Dict[str, int] | None,
        fallback_sections: Dict[str, Section],
        allowed_sections: Set[str],
    ) -> Dict[str, Section]:
        requests = builder.build_prompt_requests(
            manifest,
            signals,
            sections=section_names,
            contexts=contexts,
            token_budgets=token_budgets,
        )

        generated: Dict[str, Section] = {}
        for name in section_names:
            fallback_section = fallback_sections.get(name)
            if name not in allowed_sections:
                if fallback_section:
                    generated[name] = self._clone_section(fallback_section, reason="llm_disabled")
                continue

            request = requests.get(name)
            if request is None:
                if fallback_section:
                    generated[name] = self._clone_section(fallback_section, reason="missing_prompt_request")
                continue

            outline_prompt = request.metadata.get("outline_prompt")
            system_prompt = next((m.content for m in request.messages if m.role == "system"), None)
            user_messages = [m.content for m in request.messages if m.role == "user"]
            prompt_text = "\n\n".join(user_messages)

            self.logger.info("Generating README section via LLM: %s", name)
            try:
                response = runner.run(prompt_text, system=system_prompt, max_tokens=request.max_tokens)
            except RuntimeError as exc:
                self.logger.warning("LLM runner failed for section %s: %s", name, exc)
                if fallback_section:
                    generated[name] = self._clone_section(fallback_section, reason="llm_error")
                continue

            body = response.strip()
            if not body:
                if fallback_section:
                    generated[name] = self._clone_section(fallback_section, reason="llm_empty")
                continue
            if name in {"quickstart", "configuration", "build_and_test"} and self._looks_like_structured_payload(body):
                if fallback_section:
                    generated[name] = self._clone_section(fallback_section, reason="llm_structured_payload")
                continue
            if self._looks_low_quality_section(name, body):
                if fallback_section:
                    generated[name] = self._clone_section(fallback_section, reason="llm_low_quality")
                continue
            if self._looks_like_prompt_echo(body):
                if fallback_section:
                    generated[name] = self._clone_section(fallback_section, reason="llm_prompt_echo")
                continue
            if outline_prompt:
                outline_lines = [item.strip("- *") for item in outline_prompt.splitlines() if item.strip()]
                if outline_lines:
                    matched_outline = sum(1 for item in outline_lines if item and item in body)
                    if matched_outline >= max(1, len(outline_lines) - 1):
                        if fallback_section:
                            generated[name] = self._clone_section(fallback_section, reason="llm_outline_echo")
                        continue

            title = SECTION_TITLES.get(name, name.replace("_", " ").title())
            metadata = dict(request.metadata)
            metadata.pop("outline_prompt", None)
            metadata["llm"] = True
            metadata["token_budget"] = request.max_tokens
            generated[name] = Section(
                name=name,
                title=title,
                body=body,
                metadata=metadata,
            )
        return generated


    @staticmethod
    def _clone_section(section: Section, *, reason: str | None = None, mark_llm: bool = True) -> Section:
        metadata = dict(section.metadata)
        if mark_llm:
            metadata.setdefault("llm", False)
            if reason:
                metadata["llm_fallback_reason"] = reason
        return Section(name=section.name, title=section.title, body=section.body, metadata=metadata)

    @staticmethod
    def _clone_sections(sections: Dict[str, Section]) -> Dict[str, Section]:
        return {name: Orchestrator._clone_section(section, mark_llm=False) for name, section in sections.items()}

    @staticmethod
    def _looks_like_prompt_echo(body: str) -> bool:
        if not body:
            return True
        markers = ("Project:", "Section:", "Outline and emphasis:", "Key signals (JSON):", "Context snippets:")
        marker_hits = sum(1 for marker in markers if marker in body)
        if marker_hits >= 2:
            return True
        if body.strip().startswith("Project:"):
            return True
        if body.count("# Repository Guidelines") >= 3:
            return True
        return False

    @staticmethod
    def _looks_like_structured_payload(body: str) -> bool:
        sample = body.strip()
        if not sample:
            return False
        if sample.startswith("{") and sample.endswith("}"):
            return True
        if sample.startswith("[") and sample.endswith("]"):
            return True
        if sample.startswith("{") and '"steps"' in sample:
            return True
        if sample.startswith("[") and '"title"' in sample:
            return True
        if sample.count('"') >= 4 and ":" in sample and sample.count("\n") < 4:
            return True
        return False

    @staticmethod
    def _looks_low_quality_section(name: str, body: str) -> bool:
        plain = body.strip()
        if not plain:
            return True
        lowered = plain.lower()
        if "i'm ready" in lowered or "how can i help" in lowered:
            return True
        if name == "features" and "- " not in plain and "* " not in plain:
            return True
        if name == "features":
            lines = [line for line in plain.splitlines() if line.strip()]
            if not any(line.lstrip().startswith(('- ', '* ')) for line in lines):
                return True
        if name == "architecture":
            if "### " not in plain and "```mermaid" not in plain and "| ---" not in plain:
                return True
        return False

    @staticmethod
    def _apply_validation_fallback(
        error: ValidationError,
        sections: Dict[str, Section],
        fallbacks: Mapping[str, Section],
    ) -> bool:
        replaced = False
        for issue in error.issues:
            name = issue.section
            fallback = fallbacks.get(name)
            if fallback is None:
                continue
            current = sections.get(name)
            if current is not None:
                metadata = current.metadata if isinstance(current.metadata, dict) else {}
                if metadata.get("llm") is False and metadata.get("llm_fallback_reason") not in {None, "validation_failed"}:
                    continue
            sections[name] = Orchestrator._clone_section(fallback, reason="validation_failed")
            replaced = True
        return replaced

    def _render_readme_from_sections(
        self,
        builder: PromptBuilder,
        manifest: RepoManifest,
        sections: Dict[str, Section],
        order: Sequence[str],
    ) -> str:
        project_name = Path(manifest.root).name or "Repository"
        intro = sections.get("intro")
        if intro is None:
            self.logger.warning("LLM runner did not produce an intro section; using stub content")
            stub = build_section_stubs(["intro"], project_name=project_name)
            intro = stub["intro"]
        ordered_sections: List[Section] = []
        for name in order:
            if name == "intro":
                continue
            section = sections.get(name)
            if section is not None:
                ordered_sections.append(section)
        if hasattr(builder, "_render_readme"):
            return builder._render_readme(project_name, intro, ordered_sections)  # type: ignore[attr-defined]
        fallback_builder = PromptBuilder()
        return fallback_builder._render_readme(project_name, intro, ordered_sections)

    def _apply_badges(self, markdown: str) -> str:
        try:
            return self.badge_manager.apply(markdown)
        except Exception as exc:  # pragma: no cover - defensive guard
            self.logger.warning("Badge manager failed: %s", exc)
            return markdown

    def _validate_links(self, markdown: str, repo_path: Path) -> List[str]:
        try:
            issues = self.link_validator.validate(markdown, root=repo_path)
        except Exception as exc:  # pragma: no cover - defensive guard
            self.logger.warning("Link validation failed: %s", exc)
            return []
        for issue in issues:
            self.logger.warning("Link issue: %s", issue)
        return issues

    def _record_scorecard(
        self,
        repo_path: Path,
        markdown: str,
        link_issues: List[str],
        *,
        dry_run: bool = False,
    ) -> Dict[str, object] | None:
        try:
            result = self.scorecard.evaluate(markdown, link_issues=link_issues)
        except Exception as exc:  # pragma: no cover - defensive guard
            self.logger.warning("Scorecard evaluation failed: %s", exc)
            return None
        if dry_run:
            self.logger.info("README score (dry-run): %s", result.get("score"))
            return result
        try:
            self.scorecard.save(repo_path, result)
        except Exception as exc:  # pragma: no cover - defensive guard
            self.logger.warning("Failed to save scorecard: %s", exc)
        else:
            self.logger.info("README score: %s", result.get("score"))
        return result

    @staticmethod
    def _render_diff(original: str, updated: str) -> str:
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile="README.md (original)",
            tofile="README.md (updated)",
        )
        return "".join(diff)

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
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
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
