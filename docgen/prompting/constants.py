"""Shared constants for README prompting and fallbacks."""

from __future__ import annotations

DEFAULT_SECTIONS: tuple[str, ...] = (
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

SECTION_TITLES: dict[str, str] = {
    "intro": "Introduction",
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


__all__ = ["DEFAULT_SECTIONS", "SECTION_TITLES"]
