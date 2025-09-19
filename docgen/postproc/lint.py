"""Linting utilities for generated markdown."""

from __future__ import annotations

from typing import List


class MarkdownLinter:
    """Validates headings, code fences, and other formatting rules."""

    def lint(self, markdown: str) -> str:
        normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")
        cleaned: List[str] = []
        in_code = False
        previous_blank = False

        for line in lines:
            stripped = line.rstrip()
            if stripped.startswith("```"):
                in_code = not in_code
                cleaned.append(stripped)
                previous_blank = False
                continue

            if not in_code:
                if stripped.startswith("#") and cleaned and cleaned[-1] != "":
                    cleaned.append("")
                if not stripped:
                    if previous_blank:
                        continue
                    previous_blank = True
                    cleaned.append("")
                    continue

            cleaned.append(stripped)
            previous_blank = False

        while cleaned and cleaned[-1] == "":
            cleaned.pop()

        return "\n".join(cleaned) + "\n"
