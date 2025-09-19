"""Linting utilities for generated markdown."""


class MarkdownLinter:
    """Validates headings, code fences, and other formatting rules."""

    def lint(self, markdown: str) -> str:
        raise NotImplementedError
