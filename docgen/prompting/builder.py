"""Builds prompts and templates for the local LLM."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from ..models import RepoManifest, Signal

_DEFAULT_SECTIONS: Sequence[str] = (
    "intro",
    "features",
    "architecture",
    "quickstart",
    "configuration",
    "build_and_test",
    "deployment",
    "troubleshooting",
    "faq",
    "license",
)

_SECTION_TITLES: Dict[str, str] = {
    "features": "Features",
    "architecture": "Architecture",
    "quickstart": "Quick Start",
    "configuration": "Configuration",
    "build_and_test": "Build & Test",
    "deployment": "Deployment",
    "troubleshooting": "Troubleshooting",
    "faq": "FAQ",
    "license": "License",
}

_ROLE_DESCRIPTIONS: Dict[str, str] = {
    "src": "Primary application and library code.",
    "test": "Automated tests that guard behavior.",
    "docs": "Project documentation assets.",
    "config": "Configuration and infrastructure files.",
    "infra": "Infrastructure as code or environment definitions.",
    "examples": "Example usages and samples.",
}


class PromptBuilder:
    """Assembles section-aware prompts from templates and signals."""

    def build(
        self,
        manifest: RepoManifest,
        signals: Iterable[Signal],
        sections: Iterable[str] | None = None,
    ) -> str:
        selected_sections = list(sections) if sections else list(_DEFAULT_SECTIONS)
        grouped = self._group_signals(signals)
        project_name = Path(manifest.root).name or "Repository"

        languages = grouped.get("language.all")
        primary_language = grouped.get("language.primary")
        language_list: List[str] = []
        if languages:
            language_list = list(languages[0].metadata.get("languages", []))
        if not language_list and primary_language:
            language_list = [primary_language[0].value]

        build_signal = self._first_signal(grouped, "build.python") or self._first_signal(
            grouped, "build.generic"
        )
        build_commands = build_signal.metadata.get("commands", []) if build_signal else []

        dependency_signal = self._first_signal(grouped, "dependencies.python")
        dependency_list: List[str] = []
        if dependency_signal:
            dependency_list = list(dependency_signal.metadata.get("packages", []))

        intro = self._build_intro(project_name, language_list)
        features = self._build_features(language_list, build_signal, dependency_list)
        architecture = self._build_architecture(manifest)
        quickstart = self._build_quickstart(build_commands)
        configuration = self._build_configuration(manifest)
        build_and_test = self._build_build_and_test(build_commands)
        deployment = self._build_deployment(manifest)
        troubleshooting = self._build_troubleshooting(project_name)
        faq = self._build_faq()
        license_section = self._build_license(manifest)

        section_content = {
            "intro": intro,
            "features": features,
            "architecture": architecture,
            "quickstart": quickstart,
            "configuration": configuration,
            "build_and_test": build_and_test,
            "deployment": deployment,
            "troubleshooting": troubleshooting,
            "faq": faq,
            "license": license_section,
        }

        lines: List[str] = [f"# {project_name}", "", intro.strip(), ""]
        for key in selected_sections:
            if key == "intro":
                continue
            heading = _SECTION_TITLES.get(key, key.replace("_", " ").title())
            content = section_content.get(key, "(section content pending)").strip()
            lines.append(f"## {heading}")
            lines.append("")
            lines.append(content if content else "(section content pending)")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

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
    def _build_intro(project_name: str, languages: Sequence[str]) -> str:
        if languages:
            if len(languages) == 1:
                language_phrase = languages[0]
            elif len(languages) == 2:
                language_phrase = " and ".join(languages)
            else:
                language_phrase = ", ".join(languages[:-1]) + f", and {languages[-1]}"
            return (
                f"{project_name} is a {language_phrase} project. This README was bootstrapped by ``docgen init``"
                " to summarize the repository at a glance. Update the overview as the project evolves."
            )
        return (
            f"{project_name} is managed with ``docgen init`` to generate documentation scaffolding. "
            "Replace this text with a concise mission statement for the repository."
        )

    @staticmethod
    def _build_features(
        languages: Sequence[str],
        build_signal: Signal | None,
        dependency_list: Sequence[str],
    ) -> str:
        items: List[str] = []
        if languages:
            items.append(f"Primary language: {', '.join(languages)}")
        if build_signal:
            build_desc = build_signal.value.capitalize()
            items.append(f"Build tooling: {build_desc}")
        if dependency_list:
            sample = ", ".join(dependency_list[:5])
            items.append(f"Dependency highlights: {sample}")
        items.append("Ready for continuous README generation via docgen.")
        return PromptBuilder._format_bullet_list(items)

    @staticmethod
    def _build_architecture(manifest: RepoManifest) -> str:
        layout: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for file in manifest.files:
            if "/" not in file.path:
                continue
            top = file.path.split("/", 1)[0]
            layout[top][file.role] += 1

        items: List[str] = []
        for top, role_counts in sorted(layout.items()):
            dominant_role = max(role_counts, key=role_counts.get)
            description = _ROLE_DESCRIPTIONS.get(dominant_role, "Project files.")
            items.append(f"`{top}/` — {description}")
        if not items:
            return "Document the project structure here."
        return PromptBuilder._format_bullet_list(items)

    @staticmethod
    def _build_quickstart(commands: Sequence[str]) -> str:
        if not commands:
            return "Document how to set up and run the project locally."
        block = "\n".join(commands)
        return f"Follow the steps below to get started:\n\n```bash\n{block}\n```"

    @staticmethod
    def _build_configuration(manifest: RepoManifest) -> str:
        config_files = [
            file.path
            for file in manifest.files
            if file.role in {"config", "infra"} or file.path.endswith((".env", ".env.example"))
        ]
        if not config_files:
            return "List configuration files or environment variables required to run the project."
        items = [f"`{path}`" for path in sorted(config_files)]
        return PromptBuilder._format_bullet_list(items)

    @staticmethod
    def _build_build_and_test(commands: Sequence[str]) -> str:
        if not commands:
            return "Capture build commands and automated test workflows."
        items = [f"`{cmd}`" for cmd in commands]
        return PromptBuilder._format_bullet_list(items)

    @staticmethod
    def _build_deployment(manifest: RepoManifest) -> str:
        paths = {file.path for file in manifest.files}
        if "Dockerfile" in paths:
            return "Container image can be built with `docker build -t <image> .`."
        return "Outline deployment strategies or hosting targets here."

    @staticmethod
    def _build_troubleshooting(project_name: str) -> str:
        items = [
            "Confirm dependencies are installed before running commands.",
            "Use `docgen update` after code changes to refresh sections automatically.",
            f"Open an issue when {project_name} requires additional diagnostics in this section.",
        ]
        return PromptBuilder._format_bullet_list(items)

    @staticmethod
    def _build_faq() -> str:
        return (
            "**Q: How is this README maintained?**\n"
            "A: Generated with `docgen init` and updated via `docgen update`.\n\n"
            "**Q: Where do I report issues?**\n"
            "A: File an issue or start a discussion in this repository."
        )

    @staticmethod
    def _build_license(manifest: RepoManifest) -> str:
        license_paths = [
            file.path for file in manifest.files if file.path.upper().startswith("LICENSE")
        ]
        if license_paths:
            return f"License details are available in `{license_paths[0]}`."
        return "Add licensing information once the project selects a license."

    @staticmethod
    def _format_bullet_list(items: Sequence[str]) -> str:
        return "\n".join(f"- {item}" for item in items)
