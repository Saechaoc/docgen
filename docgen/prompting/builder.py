"""Builds prompts and templates for the local LLM."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

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


class PromptBuilder:
    """Assembles section-aware prompts from templates and signals."""

    SYSTEM_PROMPT = (
        "You are a senior dev doc writer. Be precise. Cite repo facts only. No speculation. "
        "Never invent commands. Prefer commands detected by analyzers."
    )

    def __init__(
        self,
        templates_dir: Path | None = None,
        *,
        style: str | None = None,
        template_pack: str | None = None,
    ) -> None:
        self.templates_dir = templates_dir or Path(__file__).with_name("templates")
        self.style = (style or "comprehensive").lower()
        self.template_pack = template_pack
        if self.style not in {"concise", "comprehensive"}:
            self.style = "comprehensive"
        self._env = self._create_env(self.templates_dir)
        self._toc_placeholder = TableOfContentsBuilder.PLACEHOLDER

    def build(
        self,
        manifest: RepoManifest,
        signals: Iterable[Signal],
        sections: Iterable[str] | None = None,
        contexts: Dict[str, List[str]] | None = None,
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
        )
        return self._render_readme(project_name, intro_section, other_sections)

    def render_sections(
        self,
        manifest: RepoManifest,
        signals: Iterable[Signal],
        sections: Iterable[str],
        contexts: Dict[str, List[str]] | None = None,
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
        )

        rendered: Dict[str, Section] = {}
        if "intro" in selected_sections:
            rendered["intro"] = intro_section
        for section in other_sections:
            rendered[section.name] = section
        return rendered

    def _build_sections(
        self,
        manifest: RepoManifest,
        grouped: Dict[str, List[Signal]],
        selected_sections: Sequence[str],
        contexts: Dict[str, List[str]],
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
        intro_context = contexts.get("intro", [])
        intro_body = self._inject_context("intro", intro_body, intro_context)
        intro_meta["context"] = intro_context
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
            section_context = contexts.get(name, [])
            body = self._inject_context(name, body, section_context)
            meta["context"] = section_context
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
        if languages:
            language_phrase = self._join_languages(languages)
            framework_clause = ""
            primary_frameworks = frameworks.get(languages[0], [])
            if primary_frameworks:
                framework_clause = f" using {', '.join(primary_frameworks)}"
            body = (
                f"{project_name} is a {language_phrase} project{framework_clause}. "
                "This README was bootstrapped by ``docgen init`` to summarize the repository at a glance."
            )
        else:
            body = (
                f"{project_name} is managed with ``docgen init`` to generate documentation scaffolding. "
                "Replace this text with a concise mission statement for the repository."
            )
        return body, {"languages": languages, "frameworks": frameworks}

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
        items: List[str] = []
        if languages:
            items.append(f"Primary languages: {', '.join(languages)}")
        for language, fw in frameworks.items():
            if fw:
                items.append(f"{language} frameworks: {', '.join(fw)}")
        for ecosystem, data in dependencies.items():
            packages = data.get("packages") or data.get("dependencies")
            if isinstance(packages, list) and packages:
                items.append(f"{ecosystem} dependencies: {', '.join(packages[:5])}")
        if build_commands:
            tool_list = ", ".join(sorted(build_commands.keys()))
            items.append(f"Supported build tooling: {tool_list}")
        if entrypoints:
            labels = [ep.get("label") or ep.get("command") for ep in entrypoints]
            if labels:
                items.append(f"Entry points: {', '.join(labels[:3])}")
        if modules:
            module_summary = ", ".join(f"{mod['name']} ({mod['files']} files)" for mod in modules[:3])
            items.append(f"Key modules: {module_summary}")
        if apis:
            api_preview = ", ".join(sig.metadata.get("path", sig.value) for sig in apis[:3])
            items.append(f"API surface: {api_preview}")
        if entities:
            items.append(f"Entities detected: {', '.join(sig.value for sig in entities[:3])}")
        for pattern in patterns:
            summary = pattern.metadata.get("summary") if pattern.metadata else None
            if summary:
                items.append(summary)
        if pattern_commands:
            items.append("Infrastructure commands available: " + ", ".join(pattern_commands[:2]))
        items.append("Ready for continuous README generation via docgen.")
        display_items = self._select_items(items, max_items=4)
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
        module_list = list(modules)
        if not module_list:
            layout: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for file in manifest.files:
                parts = file.path.split("/")
                top = parts[0]
                layout[top][file.role] += 1
            for top, role_counts in sorted(layout.items()):
                module_list.append(
                    {
                        "name": top,
                        "files": sum(role_counts.values()),
                        "roles": list(role_counts.keys()),
                    }
                )

        display_entries = self._select_entries(module_list, max_items=5) if module_list else []
        if display_entries:
            lines = []
            for entry in display_entries:
                count = entry.get("files", entry.get("count", 0))
                descriptor = "file" if count == 1 else "files"
                roles = entry.get("roles") or entry.get("role") or []
                if isinstance(roles, list):
                    description = ", ".join(roles) or "Project files"
                else:
                    description = str(roles)
                name = entry.get("name") or entry.get("path") or 'module'
                suffix = "/" if name and not name.endswith("/") else ""
                lines.append(f"`{name}{suffix}` - {description} ({count} {descriptor})")
            body = self._format_bullet_list(lines)
        else:
            body = "Document the project structure here."

        if entities:
            entity_lines = []
            for entity in entities[:5]:
                metadata = entity.metadata or {}
                file = metadata.get("file")
                bases = metadata.get("bases")
                base_text = ", ".join(bases) if isinstance(bases, list) else ""
                entity_lines.append(f"- `{entity.value}` ({base_text}) — `{file}`")
            if entity_lines:
                body += "\n\nDetected entities:\n" + "\n".join(entity_lines)

        diagram = self._build_sequence_diagram(apis[:3])

        info = {
            "entries": display_entries,
            "apis": [sig.metadata for sig in apis[:5]],
            "entities": [sig.metadata for sig in entities[:5]],
            "diagram": diagram,
        }
        return body.strip(), info

    def _build_quickstart(
        self,
        *,
        build_commands: Dict[str, List[str]],
        entrypoints: List[Dict[str, object]],
        pattern_commands: List[str],
        manifest: RepoManifest,
        **_: object,
    ) -> Tuple[str, Dict[str, object]]:
        commands = self._unique_commands(build_commands)
        entrypoint_cmds = [ep.get("command") for ep in entrypoints if ep.get("command")]
        additional_commands = entrypoint_cmds + pattern_commands
        ordered: List[str] = []
        for candidate in additional_commands + commands:
            if not candidate:
                continue
            if candidate not in ordered:
                ordered.append(candidate)

        validated = self._validate_commands(commands, manifest)
        merged: List[str] = []
        for cmd in ordered:
            if cmd in commands:
                if cmd in validated and cmd not in merged:
                    merged.append(cmd)
            else:
                if cmd not in merged:
                    merged.append(cmd)
        if not merged:
            body = "Document how to set up and run the project locally."
        else:
            display = merged
            if self.style == "concise" and len(display) > 5:
                display = display[:4] + [display[-1]]
            command_block = "\n".join(display)
            body = f"Follow the steps below to get started:\n\n```bash\n{command_block}\n```"
        return body, {"commands": merged, "entrypoints": entrypoints, "pattern_commands": pattern_commands}

    def _build_configuration(
        self,
        *,
        manifest: RepoManifest,
        **_: object,
    ) -> Tuple[str, Dict[str, object]]:
        config_files = [
            file.path
            for file in manifest.files
            if file.role in {"config", "infra"} or file.path.endswith((".env", ".env.example"))
        ]
        config_files.sort()
        if not config_files:
            body = "List configuration files or environment variables required to run the project."
            display_files: List[str] = []
        else:
            display_files = self._select_items([f"`{path}`" for path in config_files], max_items=6)
            body = self._format_bullet_list(display_files)
        return body, {"files": display_files, "all_files": config_files}

    def _build_build_and_test(
        self,
        *,
        build_commands: Dict[str, List[str]],
        manifest: RepoManifest,
        **_: object,
    ) -> Tuple[str, Dict[str, object]]:
        if not build_commands:
            body = "Capture build commands and automated test workflows."
        else:
            lines = []
            for tool, commands in build_commands.items():
                validated = self._validate_commands(commands, manifest)
                if not validated:
                    continue
                lines.append(f"**{tool.capitalize()}**")
                lines.extend(f"- `{cmd}`" for cmd in validated)
                lines.append("")
            body = "\n".join(lines).strip()
        return body, {"tools": build_commands}

    def _build_deployment(
        self,
        *,
        manifest: RepoManifest,
        **_: object,
    ) -> Tuple[str, Dict[str, object]]:
        paths = {file.path for file in manifest.files}
        docker = "Dockerfile" in paths
        if docker:
            body = "Container image can be built with `docker build -t <image> .`."
        else:
            body = "Outline deployment strategies or hosting targets here."
        return body, {"docker": docker}

    def _build_troubleshooting(
        self,
        *,
        manifest: RepoManifest,
        **_: object,
    ) -> Tuple[str, Dict[str, object]]:
        project_name = Path(manifest.root).name or "Repository"
        items = [
            "Confirm dependencies are installed before running commands.",
            "Use `docgen update` after code changes to refresh sections automatically.",
            f"Open an issue when {project_name} requires additional diagnostics in this section.",
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

    @staticmethod
    def _inject_context(name: str, body: str, contexts: List[str]) -> str:
        if not contexts:
            return body
        highlights = [snippet.strip() for snippet in contexts if snippet.strip()]
        if not highlights:
            return body
        lines = ["> Context highlights:"]
        for snippet in highlights:
            snippet_line = snippet.replace("\n", " ").strip()
            lines.append(f"> {snippet_line}")
        context_block = "\n".join(lines)
        if body.strip():
            return f"{body}\n\n{context_block}"
        return context_block

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
