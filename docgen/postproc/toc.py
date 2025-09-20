"""Automatic table-of-contents generation."""

from __future__ import annotations

import re
from typing import List


class TableOfContentsBuilder:
    """Builds ToC blocks up to level three as required by the spec."""

    PLACEHOLDER = "<!-- docgen:toc -->"

    def build(self, markdown: str) -> str:
        toc_block = self._build_block(markdown)
        if not toc_block:
            return markdown.replace(self.PLACEHOLDER, "", 1)
        begin = "<!-- docgen:begin:toc -->"
        end = "<!-- docgen:end:toc -->"
        if begin in markdown and end in markdown:
            pre, rest = markdown.split(begin, 1)
            _, post = rest.split(end, 1)
            return f"{pre}{toc_block}{post}"
        if self.PLACEHOLDER in markdown:
            return markdown.replace(self.PLACEHOLDER, toc_block, 1)
        return toc_block + "\n" + markdown

    def _build_block(self, markdown: str) -> str:
        lines = markdown.splitlines()
        headings: List[tuple[int, str, str]] = []
        in_code = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            match = re.match(r"^(#{2,3})\s+(.*)$", stripped)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                anchor = self._slugify(title)
                headings.append((level, title, anchor))

        if not headings:
            return ""

        output: List[str] = ["<!-- docgen:begin:toc -->", "## Table of Contents"]
        for level, title, anchor in headings:
            indent = "  " * (level - 2)
            output.append(f"{indent}- [{title}](#{anchor})")
        output.append("<!-- docgen:end:toc -->")
        return "\n".join(output)

    @staticmethod
    def _slugify(title: str) -> str:
        slug = title.lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"\s+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")
