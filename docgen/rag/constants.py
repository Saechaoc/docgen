"""Constants for RAG-lite indexing and retrieval."""

from __future__ import annotations

from typing import Dict, List

SECTION_TAGS: Dict[str, List[str]] = {
    "intro": ["readme", "docs"],
    "features": ["docs", "source"],
    "architecture": ["source", "docs"],
    "quickstart": ["readme", "build"],
    "configuration": ["config", "docs"],
    "build_and_test": ["build", "docs"],
    "deployment": ["infra", "docs"],
    "troubleshooting": ["docs"],
    "faq": ["docs"],
    "license": ["license", "docs"],
}

TAG_SECTIONS: Dict[str, List[str]] = {}
for section, tags in SECTION_TAGS.items():
    for tag in tags:
        TAG_SECTIONS.setdefault(tag, []).append(section)
