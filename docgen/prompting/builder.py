"""Builds prompts and templates for the local LLM."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

try:  # pragma: no cover - optional dependency
    from jinja2 import Environment, FileSystemLoader, TemplateNotFound
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    Environment = None
    TemplateNotFound = Exception  # type: ignore[assignment]

from ..models import RepoManifest, Signal
from ..postproc.toc import TableOfContentsBuilder
from .constants import DEFAULT_SECTIONS, SECTION_TITLES

_ROLE_DESCRIPTIONS: Dict[str, str] = {
    "src": "Primary application and library code",
    "test": "Automated tests that guard behaviour",
    "docs": "Project documentation assets",
    "config": "Configuration and infrastructure files",
    "infra": "Infrastructure as code or environment definitions",
    "examples": "Example usages and samples",
}


@dataclass
class Section:
    """Rendered README section details."""

    name: str
    title: str
    body: str
    metadata: Dict[str, object]


@dataclass(frozen=True)
class PromptMessage:
    """Represents a single chat message for LLM prompting."""

    role: str
    content: str


@dataclass
class PromptRequest:
    """Encapsulates an LLM prompt request for a README section."""

    section: str
    messages: List[PromptMessage]
    max_tokens: int | None
    metadata: Dict[str, object] = field(default_factory=dict)


class PromptBuilder:
    """Assembles section-aware prompts from templates and signals."""

    SYSTEM_PROMPT = (
        "You are a senior developer documentation writer. Stay grounded in repository facts. "
        "Follow the requested outline, keep explanations crisp, and never invent commands or tools."
    )

    def __init__(
        self,
        templates_dir: Path | None = None,
        *,
        style: str | None = None,
        template_pack: str | None = None,
        token_budget_default: int | None = None,
        token_budget_overrides: Dict[str, int] | None = None,
    ) -> None:
        self.templates_dir = templates_dir or Path(__file__).with_name("templates")
        self.style = (style or "comprehensive").lower()
        self.template_pack = template_pack
        if self.style not in {"concise", "comprehensive"}:
            self.style = "comprehensive"
        self._env = self._create_env(self.templates_dir)
        self._toc_placeholder = TableOfContentsBuilder.PLACEHOLDER
        self._token_budget_default = token_budget_default
        self._token_budget_overrides = token_budget_overrides or {}

    def build(
        self,
        manifest: RepoManifest,
        signals: Iterable[Signal],
        sections: Iterable[str] | None = None,
        contexts: Dict[str, List[str]] | None = None,
        *,
        token_budgets: Dict[str, int] | None = None,
    ) -> str:
        selected_sections = self._normalise_section_order(sections)
        if not selected_sections:
            selected_sections = list(DEFAULT_SECTIONS)
        grouped = self._group_signals(signals)
        project_name = Path(manifest.root).name or "Repository"

        intro_section, other_sections = self._build_sections(
            manifest,
            grouped,
            selected_sections,
            contexts or {},
            token_budgets=token_budgets,
        )
        return self._render_readme(project_name, intro_section, other_sections)

    def render_sections(
        self,
        manifest: RepoManifest,
        signals: Iterable[Signal],
        sections: Iterable[str],
        contexts: Dict[str, List[str]] | None = None,
        *,
        token_budgets: Dict[str, int] | None = None,
    ) -> Dict[str, Section]:
        selected_sections = self._normalise_section_order(sections)
        if not selected_sections:
            return {}

        grouped = self._group_signals(signals)
        intro_section, other_sections = self._build_sections(
            manifest,
            grouped,
            selected_sections,
            contexts or {},
            token_budgets=token_budgets,
        )

        rendered: Dict[str, Section] = {}
        if "intro" in selected_sections:
            rendered["intro"] = intro_section
        for section in other_sections:
            rendered[section.name] = section
        return rendered

    def build_prompt_requests(
        self,
        manifest: RepoManifest,
        signals: Iterable[Signal],
        sections: Iterable[str] | None = None,
        contexts: Dict[str, List[str]] | None = None,
        *,
        token_budgets: Dict[str, int] | None = None,
    ) -> Dict[str, PromptRequest]:
        selected_sections = self._normalise_section_order(sections)
        if not selected_sections:
            selected_sections = list(DEFAULT_SECTIONS)

        grouped = self._group_signals(signals)
        intro_section, other_sections = self._build_sections(
            manifest,
            grouped,
            selected_sections,
            contexts or {},
            token_budgets=token_budgets,
        )

        sections_by_name: Dict[str, Section] = {intro_section.name: intro_section}
        sections_by_name.update({section.name: section for section in other_sections})
        project_name = Path(manifest.root).name or "Repository"

        requests: Dict[str, PromptRequest] = {}
        for name in selected_sections:
            section = sections_by_name.get(name)
            if section is None:
                continue
            budget = self._resolve_budget(name, token_budgets)
            user_prompt, outline = self._build_user_prompt(project_name, section)
            base_metadata = dict(section.metadata)
            context_values = base_metadata.get("context", []) if isinstance(base_metadata, dict) else []
            if isinstance(context_values, Sequence) and not isinstance(context_values, (str, bytes)):
                context_count = len(context_values)
            else:
                context_count = 0
            metadata = dict(base_metadata)
            if outline:
                metadata["outline_prompt"] = outline
            metadata["style"] = self.style
            metadata["context_count"] = context_count
            if "context_truncated" in base_metadata:
                metadata["context_truncated"] = base_metadata["context_truncated"]
            if "context_budget" in base_metadata:
                metadata["context_budget"] = base_metadata["context_budget"]
            messages = [
                PromptMessage(role="system", content=self.SYSTEM_PROMPT),
                PromptMessage(role="user", content=user_prompt),
            ]
            requests[name] = PromptRequest(
                section=name,
                messages=messages,
                max_tokens=budget,
                metadata=metadata,
            )

        return requests

    def _build_sections(
        self,
        manifest: RepoManifest,
        grouped: Dict[str, List[Signal]],
        selected_sections: Sequence[str],
        contexts: Dict[str, List[str]],
        *,
        token_budgets: Dict[str, int] | None,
    ) -> Tuple[Section, List[Section]]:
        language_signal = self._first_signal(grouped, "language.all")
        languages = list(language_signal.metadata.get("languages", [])) if language_signal else []
        frameworks = self._extract_frameworks(grouped)

        build_signals = [sig for name, values in grouped.items() if name.startswith("build.") for sig in values]
        entrypoint_signals = [sig for name, values in grouped.items() if name.startswith("entrypoint.") for sig in values]
        pattern_signals = [sig for name, values in grouped.items() if name.startswith("pattern.") for sig in values]
        structure_modules = self._collect_modules(grouped)
        api_signals = grouped.get("architecture.api", [])
        entity_signals = grouped.get("architecture.entity", [])
        build_commands = self._collect_build_commands(build_signals)
        entrypoint_commands = self._collect_entrypoints(entrypoint_signals)
        pattern_commands = self._collect_pattern_commands(pattern_signals)

        dependency_signals = {
            "Python": self._first_signal(grouped, "dependencies.python"),
            "Node.js": self._first_signal(grouped, "dependencies.node"),
            "Java": self._first_signal(grouped, "dependencies.java"),
        }
        dependencies = {
            eco: sig.metadata
            for eco, sig in dependency_signals.items()
            if sig is not None
        }

        intro_body, intro_meta = self._build_intro(manifest, languages, frameworks)
        intro_context_input = list(contexts.get("intro", []))
        intro_context, intro_truncated, intro_budget = self._prepare_context(
            "intro", intro_context_input, token_budgets
        )
        intro_context_clean = self._normalise_context_snippets(intro_context)
        intro_body = self._inject_context("intro", intro_body, intro_context_clean)
        intro_meta["context"] = intro_context_clean
        intro_meta["evidence"] = self._build_section_evidence(
            intro_meta.get("evidence"),
            grouped_keys=list(grouped.keys()),
            context_count=len(intro_context_clean),
        )
        if intro_budget is not None:
            intro_meta["context_budget"] = intro_budget
        if intro_truncated:
            intro_meta["context_truncated"] = intro_truncated
        intro_rendered = self._render_section("intro", intro_body, intro_meta)
        intro_meta["token_estimate"] = self._estimate_tokens(intro_rendered)
        intro_meta["style"] = self.style
        intro_section = Section(name="intro", title="Introduction", body=intro_rendered, metadata=intro_meta)

        sections: List[Section] = []
        for name in selected_sections:
            if name == "intro":
                continue
            title = SECTION_TITLES.get(name, name.replace("_", " ").title())
            builder = getattr(self, f"_build_{name}", None)
            if builder is None:
                body, meta = "(section content pending)", {}
            else:
                body, meta = builder(
                    manifest=manifest,
                    languages=languages,
                    frameworks=frameworks,
                    build_commands=build_commands,
                    dependencies=dependencies,
                    entrypoints=entrypoint_commands,
                    patterns=pattern_signals,
                    pattern_commands=pattern_commands,
                    modules=structure_modules,
                    apis=api_signals,
                    entities=entity_signals,
                )
            section_context_input = list(contexts.get(name, []))
            section_context, truncated, budget = self._prepare_context(
                name, section_context_input, token_budgets
            )
            cleaned_context = self._normalise_context_snippets(section_context)
            body = self._inject_context(name, body, cleaned_context)
            meta["context"] = cleaned_context
            meta["evidence"] = self._build_section_evidence(
                meta.get("evidence"),
                grouped_keys=list(grouped.keys()),
                context_count=len(cleaned_context),
            )
            if budget is not None:
                meta["context_budget"] = budget
            if truncated:
                meta["context_truncated"] = truncated
            rendered = self._render_section(name, body, meta)
            meta["token_estimate"] = self._estimate_tokens(rendered)
            meta["style"] = self.style
            sections.append(Section(name=name, title=title, body=rendered, metadata=meta))

        return intro_section, sections

    def _build_intro(
        self,
        manifest: RepoManifest,
        languages: Sequence[str],
        frameworks: Dict[str, List[str]],
    ) -> Tuple[str, Dict[str, object]]:
        project_name = Path(manifest.root).name or "Repository"
        language_phrase = self._join_languages(languages) if languages else "polyglot"
        primary_frameworks = frameworks.get(languages[0], []) if languages else []
        files = {file.path for file in manifest.files}
        is_docgen = self._looks_like_docgen_repo(files, project_name)

        body_lines: List[str] = []
        metadata: Dict[str, object] = {"languages": languages, "frameworks": frameworks, "project_name": project_name}

        if is_docgen:
            framework_clause = ""
            if languages and primary_frameworks:
                framework_clause = f" using {', '.join(primary_frameworks)}"
            body_lines.append(
                f"{project_name} is a local-first README generator for polyglot repositories built primarily with {language_phrase}{framework_clause}."
            )
            body_lines.append("It scans every tracked file, emits analyzer signals, retrieves grounded context, and drives a local LLM through templated sections to keep documentation accurate.")
            body_lines.append("The overview below captures the full pipeline so contributors understand the moving pieces before running `docgen init`.")
            if any(file.path == "spec/spec.md" for file in manifest.files):
                body_lines.append("Refer to `spec/spec.md` for detailed architecture contracts and responsibilities.")
            metadata.update({"project_name": project_name})
        else:
            if primary_frameworks:
                body_lines.append(f"{project_name} is a {language_phrase} project using {', '.join(primary_frameworks)}.")
            elif languages:
                body_lines.append(f"{project_name} is a {language_phrase} project.")
            else:
                body_lines.append(f"{project_name} is a codebase managed with docgen.")
        body = " ".join(body_lines)
        return body, metadata

    def _build_features(
        self,
        *,
        manifest: RepoManifest,
        languages: Sequence[str],
        frameworks: Dict[str, List[str]],
        dependencies: Dict[str, object],
        build_commands: Dict[str, List[str]],
        entrypoints: List[Dict[str, object]],
        patterns: Sequence[Signal],
        pattern_commands: List[str],
        modules: Sequence[Dict[str, object]],
        apis: Sequence[Signal],
        entities: Sequence[Signal],
    ) -> Tuple[str, Dict[str, object]]:
        files = {file.path for file in manifest.files}
        project_name = Path(manifest.root).name or "Repository"
        is_docgen = self._looks_like_docgen_repo(files, project_name)
        items: List[str] = []

        def add(condition: bool, text: str) -> None:
            if condition:
                items.append(text)

        add("docgen/repo_scanner.py" in files,
            "**Repository manifest & caching** - `docgen/repo_scanner.py` walks the tree, respects ignore rules, and persists hashes for incremental runs.")
        add(any(path.startswith("docgen/analyzers/") for path in files),
            "**Analyzer plugin system** - `docgen/analyzers/*` emit language, build, dependency, entrypoint, and structure signals for downstream prompting.")
        add("docgen/prompting/builder.py" in files,
            "**Template-driven prompting** - `docgen/prompting/builder.py` merges signals with Jinja templates and enforces markdown style presets.")
        add("docgen/rag/indexer.py" in files,
            "**Lightweight RAG index** - `docgen/rag/indexer.py` embeds repo snippets into `.docgen/embeddings.json` for section-scoped retrieval.")
        add("docgen/llm/runner.py" in files,
            "**Local LLM enforcement** - `docgen/llm/runner.py` targets loopback runtimes (Model Runner, Ollama, llama.cpp) with token and temperature guards.")
        add(any(path.startswith("docgen/postproc/") for path in files),
            "**Post-processing contract** - `docgen/postproc/*` rebuild badges, ToC, lint markdown, validate links, and compute scorecards.")
        add("docgen/git/publisher.py" in files,
            "**Git-aware publishing** - `docgen/git/publisher.py` and `docgen/git/diff.py` map repo changes to sections and push commits or PRs.")
        add("docgen/cli.py" in files,
            "**Resilient CLI UX** - `docgen/cli.py` exposes `init`/`update` commands with verbose logging, dry-run previews, and validation toggles.")

        if languages:
            items.append(f"Primary stack: {', '.join(languages)}")
        for language, fw in frameworks.items():
            if fw:
                items.append(f"Frameworks observed for {language}: {', '.join(fw)}")
        if pattern_commands:
            items.append("Infrastructure commands available: " + ", ".join(pattern_commands[:2]))
        if build_commands:
            tool_list = ", ".join(sorted(build_commands.keys()))
            items.append(f"Supported build tooling: {tool_list}")
        if is_docgen:
            items.append("Ready for continuous README generation via docgen.")

        display_items = self._select_items(items, max_items=8)
        body = self._format_bullet_list(display_items)
        return body, {"items": display_items, "all_items": items}

    def _build_architecture(
        self,
        *,
        manifest: RepoManifest,
        modules: Sequence[Dict[str, object]] = (),
        apis: Sequence[Signal] = (),
        entities: Sequence[Signal] = (),
        **_: object,
    ) -> Tuple[str, Dict[str, object]]:
        files = {file.path for file in manifest.files}
        project_name = Path(manifest.root).name or "Repository"
        is_docgen = self._looks_like_docgen_repo(files, project_name)
        module_list = list(modules)
        if not module_list:
            layout: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for file in manifest.files:
                parts = file.path.split("/")
                if not parts:
                    continue
                top = parts[0]
                layout[top][file.role] += 1
            for top, role_counts in sorted(layout.items()):
                module_list.append(
                    {
                        "name": top,
                        "files": sum(role_counts.values()),
                        "roles": sorted(role_counts.keys()),
                    }
                )

        module_overview: List[Dict[str, object]] = []
        for entry in module_list:
            name = str(entry.get("name") or entry.get("path") or "").strip()
            if not name or name.startswith(".") or name.lower().startswith("readme"):
                continue
            roles = entry.get("roles")
            if isinstance(roles, Sequence) and not isinstance(roles, (str, bytes)):
                role_list = [str(role) for role in roles]
            elif roles:
                role_list = [str(roles)]
            else:
                role_list = []
            module_overview.append(
                {
                    "name": name,
                    "roles": role_list,
                    "files": int(entry.get("files") or entry.get("count") or 0),
                }
            )
        module_overview = module_overview[:8]

        if is_docgen:
            flow_summary_parts = [
                "The orchestrator (`docgen/orchestrator.py`) coordinates RepoScanner, analyzer plugins, the retrieval indexer, PromptBuilder, the local LLM runner, and post-processing publishers to keep README updates grounded in repository state."
            ]
            if "spec/spec.md" in files:
                flow_summary_parts.append("Contracts and component expectations live in `spec/spec.md`; keep the spec and README in sync when responsibilities change.")
            flow_summary = " ".join(flow_summary_parts)

            component_specs = [
                {
                    "layer": "CLI & logging",
                    "modules": ["docgen/cli.py", "docgen/logging.py", "docgen/failsafe.py"],
                    "purpose": "Parses `init`/`update` commands, wires verbose logging, and falls back to stub sections when prompting fails.",
                },
                {
                    "layer": "Configuration",
                    "modules": ["docgen/config.py"],
                    "purpose": "Loads `.docgen.yml`, enforces loopback-only LLM endpoints, and exposes analyzer/publishing toggles.",
                },
                {
                    "layer": "Repository scanning",
                    "modules": ["docgen/repo_scanner.py", ".docgen/manifest_cache.json"],
                    "purpose": "Builds `RepoManifest` entries, classifies file roles, and caches hashes for incremental runs.",
                },
                {
                    "layer": "Analyzer plugins",
                    "modules": ["docgen/analyzers/__init__.py", "docgen/analyzers/utils.py"],
                    "purpose": "Emit language, dependency, entrypoint, architecture, and pattern signals consumed downstream.",
                },
                {
                    "layer": "Prompting",
                    "modules": ["docgen/prompting/builder.py", "docgen/prompting/templates/readme.j2"],
                    "purpose": "Shapes section prompts, estimates token budgets, validates commands, and renders markdown scaffolds.",
                },
                {
                    "layer": "Retrieval (RAG)",
                    "modules": ["docgen/rag/indexer.py", "docgen/rag/store.py", "docgen/rag/embedder.py"],
                    "purpose": "Chunks docs/source into embeddings stored under `.docgen/embeddings.json` for section-scoped context.",
                },
                {
                    "layer": "LLM runtime",
                    "modules": ["docgen/llm/runner.py", "docgen/llm/llamacpp.py"],
                    "purpose": "Calls local model runners (Model Runner, Ollama, llama.cpp) with strict token and temperature limits.",
                },
                {
                    "layer": "Post-processing & publishing",
                    "modules": [
                        "docgen/postproc/toc.py",
                        "docgen/postproc/markers.py",
                        "docgen/postproc/badges.py",
                        "docgen/postproc/links.py",
                        "docgen/git/publisher.py",
                        "docgen/git/diff.py",
                        "docgen/postproc/scorecard.py",
                    ],
                    "purpose": "Rebuilds the ToC, repairs markers, validates links, computes scorecards, and pushes commits or PRs.",
                },
                {
                    "layer": "Service API",
                    "modules": ["docgen/service/app.py"],
                    "purpose": "Exposes health, init, and update endpoints for external orchestration or hosted runners.",
                },
            ]

            component_rows: List[Dict[str, object]] = []
            repo_root = Path(manifest.root)
            for spec in component_specs:
                present_modules = [
                    module
                    for module in spec["modules"]
                    if module in files or (repo_root / module).exists()
                ]
                if not present_modules:
                    continue
                component_rows.append(
                    {
                        "layer": spec["layer"],
                        "modules": present_modules,
                        "purpose": spec["purpose"],
                    }
                )

            flow_diagram = self._default_flow_diagram()
            init_sequence = self._default_init_sequence()
            update_sequence = self._default_update_sequence()
        else:
            flow_summary = self._build_generic_architecture_summary(module_overview, project_name)
            if "spec/spec.md" in files:
                flow_summary += " Reference `spec/spec.md` for detailed contracts."
            component_rows = self._build_generic_component_rows(module_overview)
            flow_diagram = ""
            init_sequence = ""
            update_sequence = ""

        artifacts = self._discover_artifacts(manifest)
        api_diagram = self._build_sequence_diagram(apis[:3])
        entity_rows: List[Dict[str, object]] = []
        for signal in entities[:8]:
            metadata = signal.metadata or {}
            bases = metadata.get("bases")
            base_list = [str(base) for base in bases] if isinstance(bases, list) else []
            entity_rows.append(
                {
                    "name": signal.value,
                    "file": metadata.get("file"),
                    "bases": base_list,
                }
            )

        info: Dict[str, object] = {
            "flow_summary": flow_summary,
            "flow_diagram": flow_diagram,
            "components": component_rows,
            "module_overview": module_overview,
            "artifacts": artifacts,
            "init_sequence": init_sequence,
            "update_sequence": update_sequence,
            "api_diagram": api_diagram,
            "entities": entity_rows,
        }
        return flow_summary, info

    def _discover_artifacts(self, manifest: RepoManifest) -> List[Dict[str, str]]:
        files = {file.path for file in manifest.files}
        artifacts: List[Dict[str, str]] = []

        def include(path: str, description: str) -> None:
            target = Path(manifest.root) / path
            if path in files or target.exists():
                artifacts.append({"path": path, "description": description})

        include(".docgen/manifest_cache.json", "Cache of file hashes for incremental repo scans.")
        include(".docgen/embeddings.json", "Lightweight embedding store supporting section-scoped retrieval.")
        include(".docgen/scorecard.json", "Scorecard output capturing lint, link, and coverage metrics.")
        include(".docgen/validation.json", "Validation trace covering hallucination checks and sentence-level issues.")
        include(".docgen/analyzers/cache.json", "Analyzer cache that enables incremental signal execution.")
        return artifacts

    def _build_generic_architecture_summary(
        self,
        modules: Sequence[Dict[str, object]],
        project_name: str,
    ) -> str:
        if not modules:
            return f"{project_name} combines application code with supporting documentation and configuration assets."
        module_names = [entry.get("name") for entry in modules if entry.get("name")]
        roles = {role for entry in modules for role in entry.get("roles", []) if role}
        parts: List[str] = []
        if module_names:
            display = ", ".join(module_names[:3])
            if len(module_names) > 3:
                display += ", ..."
            parts.append(f"Top-level modules such as {display} organise the project structure.")
        if roles:
            role_phrases = [
                _ROLE_DESCRIPTIONS.get(str(role), str(role).replace('_', ' '))
                for role in sorted(roles)
            ]
            parts.append(f"Roles covered include {', '.join(role_phrases)}.")
        return " ".join(parts) or f"{project_name} combines application code with supporting documentation and configuration assets."

    def _build_generic_component_rows(
        self,
        modules: Sequence[Dict[str, object]],
    ) -> List[Dict[str, object]]:
        rows: List[Dict[str, object]] = []
        for entry in modules[:6]:
            name = entry.get("name")
            if not name:
                continue
            roles = [str(role) for role in entry.get("roles", []) if role]
            if roles:
                descriptions = [
                    _ROLE_DESCRIPTIONS.get(role, role.replace('_', ' '))
                    for role in roles
                ]
                purpose = "; ".join(descriptions)
            else:
                purpose = "Application code and supporting assets."
            rows.append({"layer": str(name).replace('_', ' ').title(), "modules": [str(name)], "purpose": purpose})
        return rows

    @staticmethod
    def _default_flow_diagram() -> str:
        lines = [
            "flowchart LR",
            '    CLI["CLI (docgen init/update)"]',
            '    Orc["Orchestrator"]',
            '    Scan["RepoScanner"]',
            '    Ana["Analyzer plugins"]',
            '    RAG["RAGIndexer"]',
            '    Prompt["PromptBuilder"]',
            '    LLM["Local LLM Runner"]',
            '    Post["Post-processing"]',
            '    Pub["Publisher"]',
            '    Out["README.md + scorecards"]',
            "    CLI --> Orc",
            "    Orc --> Scan",
            "    Orc --> Ana",
            "    Orc --> RAG",
            "    Orc --> Prompt",
            "    Prompt --> LLM",
            "    LLM --> Prompt",
            "    Prompt --> Orc",
            "    Orc --> Post",
            "    Post --> Pub",
            "    Post --> Out",
        ]
        return "\n".join(lines)

    @staticmethod
    def _default_init_sequence() -> str:
        lines = [
            "sequenceDiagram",
            "    participant Dev as Developer",
            "    participant CLI as docgen CLI",
            "    participant Orc as Orchestrator",
            "    participant Scan as RepoScanner",
            "    participant Ana as Analyzer plugins",
            "    participant RAG as RAGIndexer",
            "    participant Prompt as PromptBuilder",
            "    participant LLM as LLMRunner",
            "    participant Post as Post-processing",
            "    participant FS as Filesystem",
            "    Dev->>CLI: docgen init .",
            "    CLI->>Orc: run_init(path)",
            "    Orc->>Scan: scan()",
            "    Scan-->>Orc: RepoManifest",
            "    Orc->>Ana: analyze(manifest)",
            "    Ana-->>Orc: Signal[]",
            "    Orc->>RAG: build(manifest)",
            "    RAG-->>Orc: contexts per section",
            "    Orc->>Prompt: build(...)",
            "    Prompt->>LLM: invoke prompts",
            "    LLM-->>Prompt: section drafts",
            "    Prompt-->>Orc: README draft",
            "    Orc->>Post: lint + toc + badges + links + scorecard",
            "    Post-->>Orc: polished markdown",
            "    Orc->>FS: write README.md",
        ]
        return "\n".join(lines)

    @staticmethod
    def _default_update_sequence() -> str:
        lines = [
            "sequenceDiagram",
            "    participant Dev as Developer/CI",
            "    participant CLI as docgen CLI",
            "    participant Orc as Orchestrator",
            "    participant Diff as DiffAnalyzer",
            "    participant Scan as RepoScanner",
            "    participant Ana as Analyzer plugins",
            "    participant RAG as RAGIndexer",
            "    participant Prompt as PromptBuilder",
            "    participant Mark as MarkerManager",
            "    participant Post as Post-processing",
            "    Dev->>CLI: docgen update --diff-base <ref>",
            "    CLI->>Orc: run_update(path, base)",
            "    Orc->>Diff: compute()",
            "    Diff-->>Orc: sections to refresh",
            "    Orc->>Scan: scan()",
            "    Scan-->>Orc: RepoManifest",
            "    Orc->>Ana: analyze(manifest)",
            "    Ana-->>Orc: Signal[]",
            "    Orc->>RAG: build(manifest, sections)",
            "    RAG-->>Orc: context snippets",
            "    Orc->>Prompt: render_sections(sections)",
            "    Prompt-->>Orc: refreshed markdown",
            "    Orc->>Mark: splice into README",
            "    Mark-->>Orc: patched markdown",
            "    Orc->>Post: lint + toc + badges + links + scorecard",
            "    Post-->>Orc: final README",
        ]
        return "\n".join(lines)

    def _build_quickstart(
        self,
        *,
        build_commands: Dict[str, List[str]],
        entrypoints: List[Dict[str, object]],
        pattern_commands: List[str],
        manifest: RepoManifest,
        **_: object,
    ) -> Tuple[str, Dict[str, object]]:
        root = Path(manifest.root)
        steps: List[Dict[str, object]] = []

        steps.append(
            {
                "title": "Create a virtual environment (matches PyCharm settings)",
                "commands": ["python -m venv .venv"],
            }
        )
        steps.append(
            {
                "title": "Activate the environment",
                "commands": [r".\.venv\Scripts\activate", "source .venv/bin/activate"],
                "notes": ["Use the first command on Windows PowerShell; the second works on bash or zsh."],
            }
        )
        if (root / "pyproject.toml").exists():
            steps.append(
                {
                    "title": "Install docgen in editable mode with development extras",
                    "commands": ["python -m pip install -e .[dev]"],
                    "notes": ["Exposes the CLI, analyzer plugins, and formatting toolchain without repeated reinstalls."],
                }
            )
        else:
            steps.append(
                {
                    "title": "Install dependencies once packaging metadata lands",
                    "notes": ["After `pyproject.toml` is committed, run `python -m pip install -e .[dev]` to expose the CLI and dev extras."],
                }
            )
        steps.append(
            {
                "title": "Generate the initial README",
                "commands": ["python -m docgen.cli init ."],
                "notes": ["Rename or remove an existing README before running the bootstrapper."],
            }
        )
        steps.append(
            {
                "title": "Refresh documentation after changes",
                "commands": ["python -m docgen.cli update --diff-base origin/main"],
                "notes": ["Point `--diff-base` at your default branch; add `--dry-run` to preview markdown."],
            }
        )
        steps.append(
            {
                "title": "Iterate with verbose diagnostics",
                "notes": ["Append `--verbose` to surface analyzer, retrieval, and post-processing logs during development."],
            }
        )

        build_only = self._unique_commands(build_commands)
        validated = self._validate_commands(build_only, manifest)
        entrypoint_cmds = [str(ep.get("command")) for ep in entrypoints if ep.get("command")]
        runtime_commands: List[str] = []
        for raw_cmd in validated + entrypoint_cmds + list(pattern_commands):
            if not raw_cmd:
                continue
            cmd = str(raw_cmd)
            if self._is_runtime_test_command(cmd):
                continue
            if cmd not in runtime_commands:
                runtime_commands.append(cmd)
        if runtime_commands:
            steps.append(
                {
                    "title": "Run project commands discovered by analyzers",
                    "commands": runtime_commands,
                }
            )

        metadata = {"steps": steps}
        return "", metadata

    def _build_configuration(
        self,
        *,
        manifest: RepoManifest,
        **_: object,
    ) -> Tuple[str, Dict[str, object]]:
        root = Path(manifest.root)
        files = {file.path for file in manifest.files}
        project_name = root.name or "Repository"
        is_docgen = self._looks_like_docgen_repo(files, project_name)

        tracked_paths: List[str] = []

        def add_path(path: str) -> None:
            if path not in tracked_paths:
                tracked_paths.append(path)

        docgen_candidates = [".docgen.yml", "docs/ci/docgen-update.yml", "docs/ci/github-actions.md", "docs/models.md"]
        for candidate in docgen_candidates:
            if candidate in files or (root / candidate).exists():
                add_path(candidate)

        env_files = sorted(path for path in files if path.endswith((".env", ".env.example")))
        for path in env_files:
            add_path(path)

        generic_candidates = [
            "pyproject.toml",
            "poetry.lock",
            "Pipfile",
            "Pipfile.lock",
            "requirements.txt",
            "requirements.in",
            "setup.cfg",
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "Dockerfile",
            "docker-compose.yml",
            "compose.yaml",
            "Makefile",
        ]
        for candidate in generic_candidates:
            if candidate in files or (root / candidate).exists():
                add_path(candidate)

        workflow_files = sorted(path for path in files if path.startswith(".github/workflows/"))
        for path in workflow_files:
            add_path(path)

        if is_docgen:
            summary = "`docgen/config.py` loads `.docgen.yml` into typed dataclasses and falls back to safe defaults when the file is missing."
            config_example_lines = [
                "llm:",
                "  runner: 'model-runner'",
                "  base_url: 'http://localhost:12434/engines/v1'",
                "  model: 'ai/smollm2:360M-Q4_K_M'",
                "  temperature: 0.2",
                "  max_tokens: 2048",
                "",
                "readme:",
                "  style: 'comprehensive'",
                "  token_budget:",
                "    default: 2048",
                "",
                "publish:",
                "  mode: 'pr'",
                "  branch_prefix: 'docgen/readme-update'",
                "  labels: ['docs:auto']",
                "",
                "analyzers:",
                "  exclude_paths:",
                "    - 'sandbox/'",
                "",
                "ci:",
                "  watched_globs:",
                "    - 'docgen/**'",
                "    - 'docs/**'",
            ]
            config_example = "\n".join(config_example_lines)
            notes = [
                "Environment overrides (`DOCGEN_LLM_MODEL`, `DOCGEN_LLM_BASE_URL`, `DOCGEN_LLM_API_KEY`) take precedence at runtime.",
                "LLM endpoints must resolve to loopback or internal hosts; remote URLs are rejected by `LLMRunner`.",
                "Analyzer include/exclude settings keep noisy directories out of signal generation.",
                "Validation defaults enable the no-hallucination guard; disable it only for diagnostics.",
            ]
        else:
            summary = ""
            if tracked_paths:
                display = ", ".join(tracked_paths[:3])
                if len(tracked_paths) > 3:
                    display += ", ..."
                summary = f"Configuration assets live in {display}."
            config_example = None
            notes: List[str] = []
            if any(path.endswith((".env", ".env.example")) for path in tracked_paths):
                notes.append("Duplicate sensitive values into a local `.env` file before running services.")
            if any(path.startswith(".github/workflows/") for path in tracked_paths):
                notes.append("GitHub Actions workflows define CI/CD checks; update them alongside code changes.")
            if any(tp.endswith(("Dockerfile", "docker-compose.yml", "compose.yaml")) for tp in tracked_paths):
                notes.append("Container and compose files document how to run the stack consistently.")
            if not summary:
                summary = "Surface key runtime and deployment configuration files here."

        metadata = {
            "summary": summary,
            "files": tracked_paths,
            "config_example": config_example,
            "notes": notes,
        }
        return summary, metadata


    def _build_build_and_test(
        self,
        *,
        build_commands: Dict[str, List[str]],
        pattern_commands: Sequence[str],
        manifest: RepoManifest,
        **_: object,
    ) -> Tuple[str, Dict[str, object]]:
        files = {file.path for file in manifest.files}
        project_name = Path(manifest.root).name or "Repository"
        is_docgen = self._looks_like_docgen_repo(files, project_name)

        if is_docgen:
            workflows: List[Dict[str, object]] = [
                {
                    "title": "Format & lint",
                    "commands": ["black docgen tests", "python -m ruff check docgen tests"],
                },
                {
                    "title": "Type-check core modules",
                    "commands": ["python -m mypy docgen"],
                },
                {
                    "title": "Run the full test suite",
                    "commands": ["python -m pytest"],
                    "notes": ["Covers CLI, orchestrator, analyzers, prompting, git, RAG, and post-processing modules."],
                },
                {
                    "title": "Iterate on specific components",
                    "commands": [
                        "python -m pytest -k orchestrator",
                        "python -m pytest tests/analyzers/test_structure.py",
                    ],
                },
            ]
        else:
            workflows = []

            unique_commands = self._unique_commands(build_commands)
            validated = self._validate_commands(unique_commands, manifest)
            combined: List[str] = []
            for raw in validated + [str(cmd) for cmd in pattern_commands]:
                cmd = str(raw).strip()
                if not cmd or cmd in combined:
                    continue
                combined.append(cmd)

            lint_keywords = ("lint", "format", "ruff", "flake", "black", "eslint", "prettier", "pylint")
            type_keywords = ("mypy", "pyright", "tsc", "type-check", "typecheck")
            build_keywords = ("build", "compile", "bundle", "dist", "package")

            lint_commands: List[str] = []
            type_commands: List[str] = []
            test_commands: List[str] = []
            build_cmds: List[str] = []
            runtime_commands: List[str] = []

            for cmd in combined:
                lower = cmd.lower()
                if self._is_runtime_test_command(cmd):
                    test_commands.append(cmd)
                    continue
                if any(keyword in lower for keyword in lint_keywords):
                    lint_commands.append(cmd)
                    continue
                if any(keyword in lower for keyword in type_keywords):
                    type_commands.append(cmd)
                    continue
                if any(keyword in lower for keyword in build_keywords):
                    build_cmds.append(cmd)
                    continue
                runtime_commands.append(cmd)

            if lint_commands:
                workflows.append({"title": "Format & lint", "commands": lint_commands[:4]})
            if type_commands:
                workflows.append({"title": "Type-check", "commands": type_commands[:4]})
            if test_commands:
                workflows.append({"title": "Run tests", "commands": test_commands[:4]})
            if build_cmds:
                workflows.append({"title": "Build artifacts", "commands": build_cmds[:4]})
            if runtime_commands:
                workflows.append({"title": "Runtime commands", "commands": runtime_commands[:4]})
            if not workflows:
                workflows.append(
                    {
                        "title": "Document project workflows",
                        "notes": ["Extend docgen analyzers to surface build and test commands automatically."],
                    }
                )

        base_commands = {
            cmd
            for item in workflows
            for cmd in item.get("commands", [])
        }

        extra_commands: List[str] = []
        for commands in build_commands.values():
            validated = self._validate_commands(commands, manifest)
            for cmd in validated:
                if cmd not in base_commands and cmd not in extra_commands:
                    extra_commands.append(cmd)

        metadata = {
            "workflows": workflows,
            "extra_commands": extra_commands[:6],
        }
        return "", metadata


    def _build_deployment(
        self,
        *,
        manifest: RepoManifest,
        **_: object,
    ) -> Tuple[str, Dict[str, object]]:
        root = Path(manifest.root)
        files = {file.path for file in manifest.files}
        project_name = root.name or "Repository"
        is_docgen = self._looks_like_docgen_repo(files, project_name)

        bullets: List[str] = []
        if is_docgen:
            if (root / "docs/ci/docgen-update.yml").exists():
                bullets.append("`docs/ci/docgen-update.yml` installs the package in editable mode, runs `docgen update`, and can push README changes from CI.")
            if (root / "docs/ci/github-actions.md").exists():
                bullets.append("`docs/ci/github-actions.md` documents required secrets and explains the scheduled workflow for README refreshes.")
            if (root / "docgen/git/publisher.py").exists():
                bullets.append("`Publisher` integrates with the GitHub CLI when `publish.mode` is set to `pr`; use `publish.mode: commit` for bootstrap automation.")
            bullets.append("Run docgen against a loopback model runner such as Model Runner at `http://localhost:12434/engines/v1` or Ollama to keep data local.")
            bullets.append("Add Docker or Compose manifests alongside analyzer pattern signals so deployment commands surface automatically in Quick Start.")
        else:
            if any(path.startswith(".github/workflows/") for path in files):
                bullets.append("GitHub Actions workflows under `.github/workflows/` coordinate tests and deployments; keep README guidance aligned with those jobs.")
            if any(fp.endswith(("Dockerfile", "docker-compose.yml", "compose.yaml")) for fp in files):
                bullets.append("Container manifests (`Dockerfile`, `docker-compose.yml`) enable parity between local and production environments.")
            if any(path.endswith(".tf") or path.startswith("infra/") for path in files):
                bullets.append("Infrastructure-as-code assets should have documented plan/apply steps in your release pipeline.")
            if any(path.endswith(".yaml") and "k8s" in path.lower() for path in files):
                bullets.append("Kubernetes manifests require cluster credentials; note the target namespaces and rollout commands.")
            if not bullets:
                bullets.append("Capture deployment targets (e.g., cloud provider, container registry, package index) and the commands required to publish new versions.")

        metadata = {"bullets": bullets}
        return "", metadata


    def _build_troubleshooting(
        self,
        *,
        manifest: RepoManifest,
        **_: object,
    ) -> Tuple[str, Dict[str, object]]:
        project_name = Path(manifest.root).name or "Repository"
        files = {file.path for file in manifest.files}
        is_docgen = self._looks_like_docgen_repo(files, project_name)
        if is_docgen:
            items = [
                "Confirm dependencies are installed before running commands.",
                "Use `docgen update` after code changes to refresh sections automatically.",
                f"Open an issue when {project_name} requires additional diagnostics in this section.",
            ]
        else:
            items = [
                "Confirm dependencies are installed before running commands.",
                "Review recent CI failures or local test runs for failing components.",
                "Increase logging verbosity or enable debug flags to capture more context when issues persist.",
            ]
        display_items = self._select_items(items, max_items=5)
        return self._format_bullet_list(display_items), {"items": display_items, "all_items": items}


    def _build_faq(
        self,
        **_: object,
    ) -> Tuple[str, Dict[str, object]]:
        qa = [
            {
                "question": "How is this README maintained?",
                "answer": "Generated with `docgen init` and updated via `docgen update`.",
            },
            {
                "question": "Where do I report issues?",
                "answer": "File an issue or start a discussion in this repository.",
            },
        ]
        body_lines = []
        for item in qa:
            body_lines.append(f"**Q: {item['question']}**")
            body_lines.append(f"A: {item['answer']}")
            body_lines.append("")
        body = "\n".join(body_lines).strip()
        return body, {"qa": qa}

    def _build_license(
        self,
        *,
        manifest: RepoManifest,
        **_: object,
    ) -> Tuple[str, Dict[str, object]]:
        license_paths = [
            file.path for file in manifest.files if file.path.upper().startswith("LICENSE")
        ]
        if license_paths:
            body = f"License details are available in `{license_paths[0]}`."
        else:
            body = "Add licensing information once the project selects a license."
        return body, {"files": license_paths}

    def _prepare_context(
        self,
        section: str,
        snippets: List[str],
        token_budgets: Dict[str, int] | None,
    ) -> Tuple[List[str], int, int | None]:
        budget = self._resolve_budget(section, token_budgets)
        if budget is None or budget <= 0:
            return [snippet for snippet in snippets if snippet.strip()], 0, budget

        trimmed: List[str] = []
        total_tokens = 0
        truncated = 0
        for snippet in snippets:
            content = snippet.strip()
            if not content:
                continue
            tokens = self._estimate_tokens(content)
            if tokens <= 0:
                continue
            if total_tokens + tokens > budget:
                truncated += 1
                continue
            trimmed.append(content)
            total_tokens += tokens
        return trimmed, truncated, budget

    def _resolve_budget(self, section: str, overrides: Dict[str, int] | None) -> int | None:
        if overrides and section in overrides:
            return overrides[section]
        if section in self._token_budget_overrides:
            return self._token_budget_overrides[section]
        if overrides and "default" in overrides:
            return overrides["default"]
        return self._token_budget_default

    @staticmethod
    def _inject_context(name: str, body: str, contexts: List[str]) -> str:
        """Leave README body untouched; contexts live in metadata for LLM consumption."""
        return body

    @staticmethod
    def _normalise_context_snippets(snippets: Sequence[str], *, limit: int = 3) -> List[str]:
        cleaned: List[str] = []
        for snippet in snippets:
            text = " ".join(str(snippet).strip().split())
            if not text:
                continue
            cleaned.append(text)
            if len(cleaned) >= limit:
                break
        return cleaned

    @staticmethod
    def _validate_commands(commands: Sequence[str], manifest: RepoManifest) -> List[str]:
        validated: List[str] = []
        available_paths = {file.path for file in manifest.files}
        root = Path(manifest.root)
        for command in commands:
            if not command.strip():
                continue
            if _command_is_known(command):
                validated.append(command)
                continue
            referenced_paths = _extract_paths_from_command(command)
            if not referenced_paths:
                validated.append(command)
                continue
            exists = False
            for rel_path in referenced_paths:
                normalised = Path(rel_path).as_posix()
                if normalised in available_paths:
                    exists = True
                    break
                if (root / rel_path).exists():
                    exists = True
                    break
            if exists:
                validated.append(command)
        return validated

    @staticmethod
    def _normalise_section_order(sections: Iterable[str] | None) -> List[str]:
        if sections is None:
            return []
        requested = {section for section in sections if section in DEFAULT_SECTIONS}
        return [section for section in DEFAULT_SECTIONS if section in requested]

    def _render_section(self, name: str, body: str, metadata: Dict[str, object]) -> str:
        if not self._env:
            return body
        template_name = f"sections/{name}.j2"
        try:
            template = self._env.get_template(template_name)
        except TemplateNotFound:  # type: ignore[misc]
            template = self._env.get_template("sections/default.j2")
        return template.render(body=body, metadata=metadata)

    def _render_readme(self, project_name: str, intro: Section, sections: List[Section]) -> str:
        if not self._env:
            lines: List[str] = [f"# {project_name}", "", self._toc_placeholder, "", intro.body.strip(), ""]
            for section in sections:
                lines.append(f"## {section.title}")
                lines.append("")
                lines.append(section.body.strip())
                lines.append("")
            return "\n".join(lines).strip() + "\n"

        template = self._env.get_template("readme.j2")
        return (
            template.render(
                project_name=project_name,
                toc_placeholder=self._toc_placeholder,
                intro={"body": intro.body, "metadata": intro.metadata},
                sections=[
                    {"name": section.name, "title": section.title, "body": section.body, "metadata": section.metadata}
                    for section in sections
                ],
            ).strip()
            + "\n"
        )

    def _build_user_prompt(self, project_name: str, section: Section) -> tuple[str, str | None]:
        metadata_copy = dict(section.metadata)
        contexts = metadata_copy.pop("context", [])
        truncated = metadata_copy.get("context_truncated")
        snapshot = self._build_metadata_snapshot(section.name, metadata_copy)

        lines = [
            f"Project: {project_name}",
            f"Section: {section.title}",
            "Write the markdown body for this section using only repository-derived facts.",
            "Follow the requested outline and keep the tone instructional but concise.",
        ]

        outline = self._build_section_outline(section.name, project_name, snapshot)
        if outline:
            lines.append("Outline and emphasis:")
            lines.append(outline)

        if snapshot:
            metadata_json = json.dumps(snapshot, indent=2, sort_keys=True)
            lines.append("Key signals (JSON):")
            lines.append(metadata_json)

        if contexts:
            lines.append("Context snippets:")
            for snippet in contexts:
                cleaned = snippet.replace("\n", " ").strip()
                if not cleaned:
                    continue
                lines.append(f"- {cleaned}")
        else:
            lines.append("Context snippets: (none)")

        if truncated:
            lines.append(f"(Additional context snippets were omitted due to token budget limits: {truncated})")

        lines.append("Return only the markdown content for this section, without extra commentary.")
        return "\n".join(lines), outline

    def _build_metadata_snapshot(self, section: str, metadata: Dict[str, object]) -> Dict[str, object]:
        snapshot: Dict[str, object] = {}
        for key, value in metadata.items():
            if key in {"context_truncated", "context_budget", "style", "token_estimate", "evidence", "llm", "token_budget"}:
                continue
            if isinstance(value, list):
                snapshot[key] = value[:6]
            elif isinstance(value, dict):
                snapshot[key] = {inner_key: value[inner_key] for idx, inner_key in enumerate(value) if idx < 6}
            else:
                snapshot[key] = value
        return snapshot

    def _build_section_outline(self, section: str, project_name: str, metadata: Dict[str, object]) -> str:
        if section == "intro":
            lines_intro = [
                f"- Summarise what {project_name} does at a product level.",
                "- Mention the main languages and frameworks when available.",
                "- Explain that docgen analyses the repository, builds context, and generates the README locally.",
            ]
            return "\n".join(lines_intro)

        outline_map = {
            "features": [
                "- Provide 5-6 bullet points covering analyzers, templating, retrieval, LLM enforcement, post-processing, and publishing.",
                "- Reference concrete modules or files when they exist.",
            ],
            "architecture": [
                "- Use subsections: `### High-Level Flow`, `### Component Responsibilities`, `### Artifacts and Data Stores`.",
                "- Add `### Pipeline Sequence (docgen init)`, `### Patch Sequence (docgen update)`, and `### API Signal Extraction`.",
                "- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.",
                "- Include available Mermaid diagrams or tables when metadata provides them.",
            ],
            "quickstart": [
                "- Present numbered setup steps plus fenced command blocks for installation, linting, tests, and docgen commands.",
            ],
            "configuration": [
                "- Highlight key configuration files (e.g., `.docgen.yml`) and environment variables.",
                "- Mention how users can toggle analyzers, templates, and publish modes.",
            ],
            "build_and_test": [
                "- Group commands by tooling (formatter, lint, type-check, test).",
                "- Format each command as an inline-code bullet.",
            ],
            "deployment": [
                "- Explain automation or CI workflows that publish README updates.",
                "- Mention container or packaging options if detected.",
            ],
            "troubleshooting": [
                "- Provide 4-5 actionable diagnostics tips, focusing on verbose logs, cache resets, and reruns after fixes.",
            ],
            "faq": [
                "- Supply bolded questions with concise answers about maintenance, LLM usage, customization, and support.",
            ],
            "license": [
                "- State the current licensing status and reference the license file once available.",
            ],
        }

        outline = outline_map.get(section)
        if outline:
            return "\n".join(outline)
        return ""

    def _create_env(self, templates_dir: Path | None) -> Environment | None:
        if Environment is None:
            return None
        directories = []
        if templates_dir:
            directories.append(str(templates_dir))
        default_dir = Path(__file__).with_name("templates")
        if self.template_pack:
            pack_dir = default_dir / self.template_pack
            directories.append(str(pack_dir))
        directories.append(str(default_dir))
        # ensure uniqueness preserving order
        seen: set[str] = set()
        ordered: list[str] = []
        for directory in directories:
            if directory not in seen:
                ordered.append(directory)
                seen.add(directory)
        loader = FileSystemLoader(ordered)
        return Environment(loader=loader, autoescape=False, trim_blocks=True, lstrip_blocks=True)

    @staticmethod
    def _group_signals(signals: Iterable[Signal]) -> Dict[str, List[Signal]]:
        grouped: Dict[str, List[Signal]] = defaultdict(list)
        for signal in signals:
            grouped[signal.name].append(signal)
        return grouped

    @staticmethod
    def _first_signal(grouped: Dict[str, List[Signal]], name: str) -> Signal | None:
        items = grouped.get(name)
        return items[0] if items else None

    @staticmethod
    def _join_languages(languages: Sequence[str]) -> str:
        if len(languages) == 1:
            return languages[0]
        if len(languages) == 2:
            return " and ".join(languages)
        return ", ".join(languages[:-1]) + f", and {languages[-1]}"

    def _extract_frameworks(self, grouped: Dict[str, List[Signal]]) -> Dict[str, List[str]]:
        frameworks: Dict[str, List[str]] = {}
        for name, signals in grouped.items():
            if not name.startswith("language.frameworks."):
                continue
            language_key = name.split(".")[-1].replace("_", " ")
            for signal in signals:
                values = list(signal.metadata.get("frameworks", []))
                if values:
                    frameworks[language_key.title()] = values
        aggregate = self._first_signal(grouped, "language.frameworks")
        if aggregate and "frameworks" in aggregate.metadata:
            for lang, values in aggregate.metadata["frameworks"].items():  # type: ignore[index]
                if values:
                    frameworks.setdefault(lang, list(values))
        return frameworks

    @staticmethod
    def _collect_build_commands(build_signals: List[Signal]) -> Dict[str, List[str]]:
        commands: Dict[str, List[str]] = {}
        for signal in build_signals:
            tool = signal.value or signal.name.split(".")[-1]
            cmds = [cmd for cmd in signal.metadata.get("commands", [])]
            if cmds:
                commands.setdefault(tool, [])
                for cmd in cmds:
                    if cmd not in commands[tool]:
                        commands[tool].append(cmd)
        return commands

    @staticmethod
    def _collect_entrypoints(signals: Iterable[Signal]) -> List[Dict[str, object]]:
        entries: List[Dict[str, object]] = []
        for signal in signals:
            metadata = signal.metadata
            if not metadata:
                continue
            command = metadata.get("command")
            if not command:
                continue
            entries.append(
                {
                    "command": command,
                    "label": metadata.get("label", command),
                    "priority": metadata.get("priority", 50),
                    "framework": metadata.get("framework"),
                }
            )
        entries.sort(key=lambda item: item.get("priority", 50))
        return entries

    @staticmethod
    def _collect_pattern_commands(signals: Iterable[Signal]) -> List[str]:
        commands: List[str] = []
        for signal in signals:
            metadata = signal.metadata
            if not metadata:
                continue
            quickstart = metadata.get("quickstart")
            if isinstance(quickstart, list):
                for cmd in quickstart:
                    if isinstance(cmd, str) and cmd not in commands:
                        commands.append(cmd)
        return commands

    @staticmethod
    def _collect_modules(grouped: Dict[str, List[Signal]]) -> List[Dict[str, object]]:
        signal = PromptBuilder._first_signal(grouped, "architecture.modules")
        if signal and signal.metadata:
            modules = signal.metadata.get("modules")
            if isinstance(modules, list):
                return modules
        return []

    @staticmethod
    def _build_sequence_diagram(api_signals: Sequence[Signal]) -> str:
        if not api_signals:
            return ""
        participants: set[str] = set()
        edges: List[tuple[str, str, str, str]] = []
        for sig in api_signals:
            metadata = sig.metadata or {}
            sequence = metadata.get("sequence")
            if not isinstance(sequence, list):
                continue
            for step in sequence:
                frm = step.get("from")
                to = step.get("to")
                msg = step.get("message", "")
                if not frm or not to:
                    continue
                participants.add(frm)
                participants.add(to)
                arrow = "->>" if "Response" not in msg else "-->>"
                edges.append((frm, to, arrow, msg))
        if not edges:
            return ""
        lines = ["sequenceDiagram"]
        for name in participants:
            lines.append(f"    participant {name}")
        for frm, to, arrow, msg in edges:
            lines.append(f"    {frm} {arrow} {to}: {msg}")
        return "\n".join(lines)

    @staticmethod
    def _is_runtime_test_command(command: str) -> bool:
        normalized = command.strip().lower()
        if not normalized:
            return False
        if "/tests" in normalized or "\tests" in normalized:
            return True
        if re.search(r"\btest(s|ing)?\b", normalized):
            return True
        for keyword in ("pytest", "tox", "coverage", "lint", "flake8", "mypy", "ruff", "bandit", "unittest"):
            if keyword in normalized:
                return True
        return False

    @staticmethod
    def _looks_like_docgen_repo(files: Set[str], project_name: Optional[str] = None) -> bool:
        markers = {"docgen/cli.py", "docgen/orchestrator.py", "docgen/prompting/builder.py"}
        if any(marker in files for marker in markers):
            return True
        if project_name and project_name.lower().startswith("docgen"):
            return True
        return False

    @staticmethod
    def _unique_commands(commands_by_tool: Dict[str, List[str]]) -> List[str]:
        seen: List[str] = []
        for commands in commands_by_tool.values():
            for cmd in commands:
                if cmd not in seen:
                    seen.append(cmd)
        return seen[:6]

    def _estimate_tokens(self, text: str) -> int:
        """Rudimentary token estimate based on character length."""
        cleaned = text.strip()
        if not cleaned:
            return 0
        return max(1, len(cleaned) // 4)

    @staticmethod
    def _build_section_evidence(
        existing: object,
        *,
        grouped_keys: Sequence[object],
        context_count: int,
    ) -> Dict[str, object]:
        evidence = dict(existing) if isinstance(existing, dict) else {}
        evidence["signals"] = sorted({str(key) for key in grouped_keys})
        evidence["context_chunks"] = int(context_count)
        return evidence

    def _select_items(
        self,
        items: Sequence[str],
        max_items: int | None,
    ) -> List[str]:
        entries = list(items)
        if self.style == "concise" and max_items is not None and len(entries) > max_items:
            if max_items >= 2:
                return entries[: max_items - 1] + [entries[-1]]
            return [entries[-1]]
        return entries

    def _format_bullet_list(self, items: Sequence[str]) -> str:
        return "\n".join(f"- {item}" for item in items)

    def _select_entries(
        self,
        entries: Sequence[Dict[str, object]],
        max_items: int | None,
    ) -> List[Dict[str, object]]:
        items = list(entries)
        if self.style == "concise" and max_items is not None and len(items) > max_items:
            if max_items >= 2:
                return items[: max_items - 1] + [items[-1]]
            return [items[-1]]
        return items


_KNOWN_COMMAND_PREFIXES = (
    "python -m pytest",
    "pytest",
    "npm test",
    "npm run",
    "yarn",
    "pnpm",
    "mvn",
    "gradle",
    "./mvnw",
    "./gradlew",
    "docker compose",
    "docker build",
)


def _command_is_known(command: str) -> bool:
    lowered = command.lower().strip()
    return any(lowered.startswith(prefix) for prefix in _KNOWN_COMMAND_PREFIXES)


def _extract_paths_from_command(command: str) -> List[str]:
    tokens = command.replace("=", " ").split()
    candidates: List[str] = []
    for token in tokens:
        cleaned = token.strip().strip("'\"`")
        if not cleaned or cleaned.startswith("-"):
            continue
        if cleaned in {"python", "pip", "npm", "yarn", "pnpm", "docker", "mvn", "gradle"}:
            continue
        if "/" in cleaned or cleaned.endswith((".txt", ".toml", ".yaml", ".yml", ".json", ".lock", ".cfg", ".ini")):
            candidates.append(cleaned)
        elif cleaned.startswith(".") and len(cleaned) > 1:
            candidates.append(cleaned)
    return candidates
