"""Tests for post-processing helpers."""

from __future__ import annotations

from pathlib import Path

from docgen.postproc.badges import BadgeManager
from docgen.postproc.lint import MarkdownLinter
from docgen.postproc.markers import MarkerManager, SectionContent
from docgen.postproc.links import LinkValidator
from docgen.postproc.scorecard import ReadmeScorecard
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


def test_table_of_contents_builder_slug_matches_github() -> None:
    md = (
        "# Project\n\n<!-- docgen:toc -->\n\n"
        "## Build & Test\n"
        "## Build & Test\n"
    )
    result = TableOfContentsBuilder().build(md)
    assert "- [Build & Test](#build--test)" in result
    assert "- [Build & Test](#build--test-1)" in result


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


def test_badge_manager_inserts_block() -> None:
    manager = BadgeManager()
    markdown = "# Project\n\nSome intro."
    result = manager.apply(markdown)
    assert "<!-- docgen:begin:badges -->" in result
    assert result.count("Build Status") == 1
    assert "](#" not in result


def test_markdown_linter_normalises_unicode_punctuation() -> None:
    markdown = "- Item — example“quote”"
    linted = MarkdownLinter().lint(markdown)
    assert "—" not in linted
    assert "“" not in linted
    assert "”" not in linted
    assert "- Item - example\"quote\"" in linted


def test_link_validator_detects_missing_file(tmp_path: Path) -> None:
    readme = "Refer to [Guide](docs/guide.md)."  # file missing
    issues = LinkValidator().validate(readme, root=tmp_path)
    assert issues == ["Link target not found: docs/guide.md"]


def test_readme_scorecard_reports_metrics() -> None:
    markdown = (
        "# Project\n\n"
        "<!-- docgen:begin:badges -->\nBadges\n<!-- docgen:end:badges -->\n\n"
        "<!-- docgen:begin:intro -->Intro<!-- docgen:end:intro -->\n"
        "## Quick Start\n"
        "<!-- docgen:begin:quickstart -->\n```bash\nrun\n```\n<!-- docgen:end:quickstart -->\n"
    )
    scorecard = ReadmeScorecard()
    result = scorecard.evaluate(markdown, link_issues=["missing"])
    assert "score" in result
    assert result["section_coverage"] < 1.0
    assert result["quickstart_has_commands"] is True
