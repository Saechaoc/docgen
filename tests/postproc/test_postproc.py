"""Tests for post-processing helpers."""

from __future__ import annotations

from docgen.postproc.lint import MarkdownLinter
from docgen.postproc.markers import MarkerManager, SectionContent
from docgen.postproc.toc import TableOfContentsBuilder


def test_markdown_linter_normalises_whitespace() -> None:
    markdown = "# Title\r\n\r\nText\r\n\r\n\r\n## Section\r\nContent  \r\n"
    linted = MarkdownLinter().lint(markdown)
    assert linted.endswith("\n")
    assert "\r" not in linted
    assert "  \n" not in linted
    assert "\n\n\n" not in linted


def test_table_of_contents_builder_inserts_placeholder() -> None:
    md = "# Project\n\n<!-- docgen:toc -->\n\n## Alpha\n\n### Beta\n"
    result = TableOfContentsBuilder().build(md)
    assert "## Table of Contents" in result
    assert "- [Alpha](#alpha)" in result
    assert "  - [Beta](#beta)" in result
    assert "<!-- docgen:end:toc -->" in result


def test_table_of_contents_builder_replaces_existing_block() -> None:
    md = (
        "# Project\n\n"
        "<!-- docgen:begin:toc -->\n## Table of Contents\n- [Old](#old)\n"
        "<!-- docgen:end:toc -->\n\n## Alpha\n"
    )
    result = TableOfContentsBuilder().build(md)
    assert result.count("## Table of Contents") == 1
    assert "- [Old](#old)" not in result
    assert "- [Alpha](#alpha)" in result


def test_marker_manager_wraps_and_replaces_sections() -> None:
    manager = MarkerManager()
    section = SectionContent(name="features", title="Features", body="- Item one")
    wrapped = manager.wrap(section)
    assert "<!-- docgen:begin:features -->" in wrapped
    updated = manager.replace(
        "Intro\n<!-- docgen:begin:features -->\nOld\n<!-- docgen:end:features -->\n",
        "features",
        "- Item two",
    )
    assert "Item two" in updated
    assert "Item one" not in updated
