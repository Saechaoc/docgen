"""Tests for docgen.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from docgen.config import AnalyzerConfig, CIConfig, DocGenConfig, LLMConfig, PublishConfig, load_config


def test_load_config_returns_defaults_when_missing(tmp_path: Path) -> None:
    config = load_config(tmp_path)

    assert isinstance(config, DocGenConfig)
    assert config.root == tmp_path.resolve()
    assert config.llm is None
    assert config.readme_style is None
    assert config.analyzers.enabled == []
    assert config.analyzers.exclude_paths == []
    assert config.publish is None
    assert config.ci.watched_globs == []
    assert config.exclude_paths == []
    assert config.templates_dir is None


def test_load_config_parses_expected_fields(tmp_path: Path) -> None:
    config_file = tmp_path / ".docgen.yml"
    config_file.write_text(
        """
llm:
  runner: "ollama"
  model: "llama3:8b-instruct"
  temperature: 0.15
  max_tokens: 256
  base_url: "http://localhost:12434/engines/v1"
  api_key: "test-key"
  request_timeout: 60
readme:
  style: "comprehensive"
  templates_dir: "docs/templates"
publish:
  mode: "pr"
  branch_prefix: "docgen/"
analyzers:
  enabled: [language, build, dependencies]
  exclude_paths:
    - ".git/"
    - "node_modules/"
exclude_paths:
  - "sandbox/"
ci:
  watched_globs:
    - "src/**"
    - "Dockerfile"
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert isinstance(config.llm, LLMConfig)
    assert config.llm.runner == "ollama"
    assert config.llm.model == "llama3:8b-instruct"
    assert config.llm.temperature == pytest.approx(0.15)
    assert config.llm.max_tokens == 256
    assert config.llm.base_url == "http://localhost:12434/engines/v1"
    assert config.llm.api_key == "test-key"
    assert config.llm.request_timeout == pytest.approx(60.0)

    assert config.readme_style == "comprehensive"
    assert config.templates_dir == (tmp_path / "docs" / "templates")

    assert config.analyzers.enabled == ["language", "build", "dependencies"]
    assert config.analyzers.exclude_paths == [".git/", "node_modules/"]

    assert isinstance(config.publish, PublishConfig)
    assert config.publish.mode == "pr"
    assert config.publish.branch_prefix == "docgen/"

    assert isinstance(config.ci, CIConfig)
    assert config.ci.watched_globs == ["src/**", "Dockerfile"]

    assert config.exclude_paths == ["sandbox/"]


def test_load_config_fallback_parser_handles_lists(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / ".docgen.yml"
    config_file.write_text(
        """
analyzers:
  enabled:
    - language
    - build
  exclude_paths: ['dist/', 'target/']
""",
        encoding="utf-8",
    )

    import docgen.config as config_module

    monkeypatch.setattr(config_module, "_yaml", None, raising=False)

    config = load_config(config_file)

    assert config.analyzers.enabled == ["language", "build"]
    assert config.analyzers.exclude_paths == ["dist/", "target/"]
