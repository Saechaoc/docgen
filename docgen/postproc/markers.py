"""Managed marker utilities for README sections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class SectionContent:
    """Represents rendered content for a README section."""

    name: str
    title: str
    body: str


class MarkerManager:
    """Applies docgen markers for idempotent section replacement."""

    BEGIN_FMT = "<!-- docgen:begin:{key} -->"
    END_FMT = "<!-- docgen:end:{key} -->"

    def wrap(self, section: SectionContent) -> str:
        """Wrap section body with managed markers."""
        begin = self.BEGIN_FMT.format(key=section.name)
        end = self.END_FMT.format(key=section.name)
        return f"{begin}\n{section.body.rstrip()}\n{end}"

    def replace(self, markdown: str, key: str, new_body: str) -> str:
        """Replace an existing managed block in the markdown string."""
        begin = self.BEGIN_FMT.format(key=key)
        end = self.END_FMT.format(key=key)
        if begin in markdown and end in markdown:
            pre, rest = markdown.split(begin, 1)
            _, post = rest.split(end, 1)
            return f"{pre}{begin}\n{new_body.rstrip()}\n{end}{post}"
        return markdown

    def extract(self, markdown: str) -> Dict[str, str]:
        """Return a mapping of section key to current content (without markers)."""
        blocks: Dict[str, str] = {}
        start_token = "<!-- docgen:begin:"
        position = 0
        while True:
            start_index = markdown.find(start_token, position)
            if start_index == -1:
                break
            key_start = start_index + len(start_token)
            key_end = markdown.find("-->", key_start)
            if key_end == -1:
                break
            key = markdown[key_start:key_end]
            end_token = self.END_FMT.format(key=key)
            body_start = key_end + len("-->")
            end_index = markdown.find(end_token, body_start)
            if end_index == -1:
                break
            body = markdown[body_start:end_index].strip()
            blocks[key] = body
            position = end_index + len(end_token)
        return blocks
