"""Badge management for generated README files."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BadgeManager:
    """Ensures README headers include a standard badge block."""

    BADGE_BLOCK = (
        "<!-- docgen:begin:badges -->\n"
        "![Build Status](https://img.shields.io/badge/build-pending-lightgrey.svg)\n"
        "![Coverage](https://img.shields.io/badge/coverage-review--needed-lightgrey.svg)\n"
        "<!-- docgen:end:badges -->"
    )

    def apply(self, markdown: str) -> str:
        """Insert or refresh the badge block after the main title."""
        if not markdown.strip():
            return markdown

        if "<!-- docgen:begin:badges -->" in markdown:
            return self._replace_existing(markdown)

        lines = markdown.splitlines()
        if not lines:
            return markdown

        # locate first heading
        insert_index = 0
        for index, line in enumerate(lines):
            if line.startswith("# "):
                insert_index = index + 1
                break
        else:
            insert_index = 0

        badge_lines = self.BADGE_BLOCK.splitlines()
        insert_block = list(badge_lines)
        if insert_index < len(lines):
            if lines[insert_index].strip():
                insert_block.append("")
        else:
            insert_block.append("")

        lines = lines[:insert_index] + insert_block + lines[insert_index:]
        return "\n".join(lines).rstrip() + "\n"

    def _replace_existing(self, markdown: str) -> str:
        begin = "<!-- docgen:begin:badges -->"
        end = "<!-- docgen:end:badges -->"
        parts = markdown.split(begin)
        if len(parts) != 2 or end not in parts[1]:
            return markdown
        before, remainder = parts
        _, after = remainder.split(end, 1)
        before = before.rstrip("\n")
        after = after.lstrip("\n")
        parts = [before, self.BADGE_BLOCK, after]
        output = "\n".join(part for part in parts if part)
        return output.rstrip() + "\n"


__all__ = ["BadgeManager"]
