"""Fail-safe stubs for README generation when pipelines fail."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Sequence

from .prompting.builder import Section
from .prompting.constants import DEFAULT_SECTIONS, SECTION_TITLES
from .postproc.markers import MarkerManager, SectionContent
from .postproc.toc import TableOfContentsBuilder


def build_readme_stub(
    repo_path: Path,
    sections: Sequence[str] | None = None,
    *,
    reason: str | None = None,
) -> str:
    """Return a placeholder README when generation fails."""
    project_name = repo_path.name or "Repository"
    ordered_sections = _normalise_sections(sections)
    marker_manager = MarkerManager()
    cleaned_reason = _format_reason(reason)

    lines = [f"# {project_name}", "", TableOfContentsBuilder.PLACEHOLDER, ""]

    intro_body = _section_stub_body("intro", project_name, cleaned_reason)
    intro_block = marker_manager.wrap(
        SectionContent(
            name="intro",
            title=SECTION_TITLES.get("intro", "Introduction"),
            body=intro_body,
        )
    )
    lines.append(intro_block)
    lines.append("")

    for name in ordered_sections:
        if name == "intro":
            continue
        title = SECTION_TITLES.get(name, name.replace("_", " ").title())
        body = _section_stub_body(name, project_name, cleaned_reason)
        wrapped = marker_manager.wrap(SectionContent(name=name, title=title, body=body))
        lines.append(f"## {title}")
        lines.append("")
        lines.append(wrapped)
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_section_stubs(
    section_names: Iterable[str],
    *,
    project_name: str,
    reason: str | None = None,
) -> Dict[str, Section]:
    """Return fallback section objects for targeted updates."""
    cleaned_reason = _format_reason(reason)
    sections: Dict[str, Section] = {}
    for name in section_names:
        title = SECTION_TITLES.get(name, name.replace("_", " ").title())
        body = _section_stub_body(name, project_name, cleaned_reason)
        sections[name] = Section(
            name=name,
            title=title,
            body=body,
            metadata=(
                {"fallback": True, "reason": cleaned_reason}
                if cleaned_reason
                else {"fallback": True}
            ),
        )
    return sections


def _normalise_sections(sections: Sequence[str] | None) -> list[str]:
    if sections is None:
        return list(DEFAULT_SECTIONS)
    seen = []
    for name in DEFAULT_SECTIONS:
        if name in sections:
            seen.append(name)
    for name in sections:
        if name not in seen:
            seen.append(name)
    return seen


def _section_stub_body(section: str, project_name: str, reason: str | None) -> str:
    """Return instructional fallback copy for a single section."""

    helper = _STUB_BUILDERS.get(section, _default_stub_builder)
    body = helper(project_name)
    if reason:
        reason_line = f"_Generation note: {reason}. Run `docgen --verbose` for diagnostics before finalising this copy._"
        return f"{body}\n\n{reason_line}".strip()
    return body


def _default_stub_builder(project_name: str) -> str:
    return (
        "Provide a concise explanation for this section. Summarise the intent, reference the relevant files, "
        "and add next steps or links that help contributors get unblocked."
    )


def _intro_stub(project_name: str) -> str:
    return (
        f"{project_name} ships with a placeholder introduction. Describe what the project does, who it serves, "
        "and the primary technologies involved. Highlight the most important workflows so readers understand the "
        "value of cloning the repository."
    )


def _features_stub(project_name: str) -> str:
    return (
        "Introduce 4–6 capabilities that set this project apart. Focus on user-facing outcomes, critical services, "
        "and automation that reduces manual effort. Reference directories or modules (for example, `src/`, "
        "`services/`, `docs/`) so new contributors can immediately inspect the implementation."
    )


def _architecture_stub(project_name: str) -> str:
    return (
        "### High-Level Flow\n\n"
        "Diagram how requests, events, or jobs move through the system from entry point to persistence. Call out any "
        "external dependencies (APIs, queues, schedulers) that must be running.\n\n"
        "### Component Responsibilities\n\n"
        "| Component | Role | Key Files |\n"
        "| --- | --- | --- |\n"
        "| (example) API gateway | Authenticate clients and route traffic | `src/api/` |\n"
        "| (example) Worker pool | Process background jobs | `services/worker.py` |\n\n"
        "### Artifacts and Data Stores\n\n"
        "Document configuration, caches, or generated assets (for example, `.docgen/manifest_cache.json`, build artifacts, database schemas)."
    )


def _quickstart_stub(project_name: str) -> str:
    return (
        "1. Ensure Python (or the primary runtime) is installed.\n"
        "2. Create and activate a virtual environment:\n"
        "```bash\npython -m venv .venv\n.\\.venv\\Scripts\\activate  # Windows\nsource .venv/bin/activate   # macOS/Linux\n```\n"
        "3. Install project dependencies (replace with the correct package command):\n"
        "```bash\npip install -r requirements.txt\n```\n"
        "4. Run core services or start the application (for example, `python -m <module>` or `npm start`).\n"
        "5. Regenerate the README after changes with `python -m docgen.cli update --diff-base origin/main`."
    )


def _configuration_stub(project_name: str) -> str:
    return (
        "List configuration assets that influence local and production behaviour. Include `.env` files, `pyproject.toml`, "
        "Docker manifests, workflow files, and any secrets management strategy. Document the expected environment variables "
        "and how to override defaults for local testing."
    )


def _build_test_stub(project_name: str) -> str:
    return (
        "Outline how contributors lint, test, and build the project. Group commands by purpose (formatting, unit tests, integration, "
        "type checking, packaging). For example:\n\n"
        "- **Format & lint** – `black .`, `ruff check .`\n"
        "- **Run unit tests** – `python -m pytest`\n"
        "- **Type-check** – `python -m mypy src`\n"
        "- **Build artifacts** – `python -m build` or container images\n\n"
        "Mention any tooling prerequisites (Docker, Node, language runtimes)."
    )


def _deployment_stub(project_name: str) -> str:
    return (
        "Summarise deployment strategies: CI/CD workflows, promotion environments, required secrets, and release cadence. "
        "Document how to publish new versions (for example, container registry pushes, serverless deploys, or package releases) "
        "and link to infrastructure repositories when relevant."
    )


def _troubleshooting_stub(project_name: str) -> str:
    return (
        "Provide quick fixes for frequent issues: dependency installation problems, migration failures, service start errors, "
        "and test flakiness. Encourage enabling verbose logs, checking CI pipelines, and capturing environment details when "
        "opening support tickets."
    )


def _faq_stub(project_name: str) -> str:
    return (
        "**Q: How is this README maintained?**\n"
        "A: Regenerate it with `docgen init` for new projects or `docgen update` after code changes.\n\n"
        "**Q: Where do I report issues or request enhancements?**\n"
        "A: Open an issue in this repository or follow your team's escalation process.\n\n"
        "Add project-specific questions covering architecture decisions, release cadence, or operational support."
    )


def _license_stub(project_name: str) -> str:
    return (
        "State the governing license (for example, MIT, Apache 2.0, proprietary). Link to the full text under `LICENSE` and clarify "
        "any contribution requirements (CLAs, DCO, review gates)."
    )


_STUB_BUILDERS = {
    "intro": _intro_stub,
    "features": _features_stub,
    "architecture": _architecture_stub,
    "quickstart": _quickstart_stub,
    "configuration": _configuration_stub,
    "build_and_test": _build_test_stub,
    "deployment": _deployment_stub,
    "troubleshooting": _troubleshooting_stub,
    "faq": _faq_stub,
    "license": _license_stub,
}


def _format_reason(reason: str | None) -> str | None:
    if not reason:
        return None
    cleaned = " ".join(reason.strip().split())
    if not cleaned:
        return None
    return cleaned[:200] + ("…" if len(cleaned) > 200 else "")


__all__ = ["build_readme_stub", "build_section_stubs"]
