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
        SectionContent(name="intro", title=SECTION_TITLES.get("intro", "Introduction"), body=intro_body)
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
            metadata={"fallback": True, "reason": cleaned_reason} if cleaned_reason else {"fallback": True},
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
    title = SECTION_TITLES.get(section, section.replace("_", " ").title())
    if section == "intro":
        base = (
            f"{project_name} currently has a placeholder README because docgen could not gather enough "
            "signals to produce documentation automatically."
        )
    else:
        base = (
            f"docgen could not populate the {title} section automatically. Provide the relevant details manually."
        )
    if reason:
        base = f"{base} (Details: {reason})"
    return f"{base} Run `docgen --verbose` for diagnostics and rerun once issues are resolved."


def _format_reason(reason: str | None) -> str | None:
    if not reason:
        return None
    cleaned = " ".join(reason.strip().split())
    if not cleaned:
        return None
    return cleaned[:200] + ("…" if len(cleaned) > 200 else "")


__all__ = ["build_readme_stub", "build_section_stubs"]
