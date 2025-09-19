"""Automatic table-of-contents generation."""


class TableOfContentsBuilder:
    """Builds ToC blocks up to level three as required by the spec."""

    def build(self, markdown: str) -> str:
        raise NotImplementedError
