"""Tests for the prompt builder."""

from __future__ import annotations

from pathlib import Path

from docgen.analyzers.build import BuildAnalyzer
from docgen.analyzers.dependencies import DependencyAnalyzer
from docgen.analyzers.language import LanguageAnalyzer
from docgen.models import Signal
from docgen.prompting.builder import PromptBuilder
from docgen.repo_scanner import RepoScanner


def _seed_repo(root: Path) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (root / "src" / "index.js").write_text("console.log('hi');\n", encoding="utf-8")
    (root / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (root / "package.json").write_text(
        '{"name": "demo", "dependencies": {"express": "4"}}\n', encoding="utf-8"
    )


def test_prompt_builder_renders_marked_sections(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)

    manifest = RepoScanner().scan(str(repo))
    analyzers = [LanguageAnalyzer(), BuildAnalyzer(), DependencyAnalyzer()]
    signals = []
    for analyzer in analyzers:
        signals.extend(analyzer.analyze(manifest))

    builder = PromptBuilder()
    readme = builder.build(manifest, signals)

    assert "<!-- docgen:begin:intro -->" in readme
    assert "<!-- docgen:begin:features -->" in readme
    assert "<!-- docgen:toc -->" in readme


def test_prompt_builder_render_sections_subset(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)

    manifest = RepoScanner().scan(str(repo))
    analyzers = [LanguageAnalyzer(), BuildAnalyzer(), DependencyAnalyzer()]
    signals = []
    for analyzer in analyzers:
        signals.extend(analyzer.analyze(manifest))

    builder = PromptBuilder()
    sections = builder.render_sections(manifest, signals, ["intro", "deployment"])

    assert set(sections) == {"intro", "deployment"}
    assert "Python project" in sections["intro"].body
    assert sections["deployment"].body.strip()


def test_prompt_builder_architecture_includes_file_counts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)

    manifest = RepoScanner().scan(str(repo))
    analyzers = [LanguageAnalyzer(), BuildAnalyzer(), DependencyAnalyzer()]
    signals = []
    for analyzer in analyzers:
        signals.extend(analyzer.analyze(manifest))

    builder = PromptBuilder()
    sections = builder.render_sections(manifest, signals, ["architecture"])

    architecture = sections["architecture"].body
    assert "Repository Layout Snapshot" in architecture
    assert "File count" in architecture


def test_prompt_builder_injects_context_highlights(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)

    manifest = RepoScanner().scan(str(repo))
    analyzers = [LanguageAnalyzer(), BuildAnalyzer(), DependencyAnalyzer()]
    signals = []
    for analyzer in analyzers:
        signals.extend(analyzer.analyze(manifest))

    builder = PromptBuilder()
    contexts = {"architecture": ["Primary service routes requests."]}
    sections = builder.render_sections(
        manifest,
        signals,
        ["architecture"],
        contexts=contexts,
    )

    body = sections["architecture"].body
    assert "### Context Highlights" in body
    assert "Primary service routes requests" in body


def test_prompt_builder_filters_missing_commands(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)
    # remove requirements file so the command becomes invalid
    (repo / "requirements.txt").unlink()

    manifest = RepoScanner().scan(str(repo))

    commands = [
        "pip install -r requirements.txt",
        "python -m pytest",
    ]

    filtered = PromptBuilder._validate_commands(commands, manifest)
    assert "python -m pytest" in filtered
    assert all("requirements.txt" not in cmd for cmd in filtered)


def test_build_prompt_requests_includes_guardrail(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)

    manifest = RepoScanner().scan(str(repo))
    analyzers = [LanguageAnalyzer(), BuildAnalyzer(), DependencyAnalyzer()]
    signals: list[Signal] = []
    for analyzer in analyzers:
        signals.extend(analyzer.analyze(manifest))

    builder = PromptBuilder()
    requests = builder.build_prompt_requests(manifest, signals, sections=["intro"])

    intro_request = requests["intro"]
    assert intro_request.messages[0].role == "system"
    assert intro_request.messages[0].content == PromptBuilder.SYSTEM_PROMPT
    assert intro_request.messages[1].role == "user"
    assert "Project:" in intro_request.messages[1].content


def test_build_prompt_requests_applies_token_budget(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)

    manifest = RepoScanner().scan(str(repo))
    builder = PromptBuilder()
    contexts = {
        "intro": [
            "Primary service handles routing between modules.",
            "Secondary snippet that should be truncated by the budget because it is much longer than the limit and contains numerous descriptive phrases.",
        ]
    }

    requests = builder.build_prompt_requests(
        manifest,
        signals=[],
        sections=["intro"],
        contexts=contexts,
        token_budgets={"default": 30},
    )

    prompt_text = requests["intro"].messages[1].content
    assert "Primary service handles routing" in prompt_text
    assert "Secondary snippet" not in prompt_text
    assert requests["intro"].metadata["context_truncated"] == 1


def test_quickstart_includes_entrypoint_and_pattern_commands(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)

    manifest = RepoScanner().scan(str(repo))

    entry_signal = Signal(
        name="entrypoint.python.fastapi",
        value="uvicorn app.main:app --reload",
        source="entrypoints",
        metadata={
            "command": "uvicorn app.main:app --reload",
            "label": "Run FastAPI application",
            "priority": 10,
        },
    )

    pattern_signal = Signal(
        name="pattern.containerization",
        value="docker",
        source="patterns",
        metadata={
            "quickstart": ["docker compose up"],
            "summary": "Docker artifacts detected",
        },
    )

    build_signal = Signal(
        name="build.python",
        value="python",
        source="build",
        metadata={"commands": ["python -m pytest"]},
    )

    builder = PromptBuilder()
    sections = builder.render_sections(
        manifest,
        signals=[entry_signal, pattern_signal, build_signal],
        sections=["quickstart"],
    )

    quickstart = sections["quickstart"].body
    assert "uvicorn app.main:app --reload" in quickstart
    assert "docker compose up" in quickstart
    assert "python -m pytest" not in quickstart


def test_prompt_builder_concise_style_limits_feature_list(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_repo(repo)

    manifest = RepoScanner().scan(str(repo))

    signals = [
        Signal(
            name="language.all",
            value="languages",
            source="test",
            metadata={"languages": ["Python", "JavaScript", "Go", "Rust"]},
        ),
        Signal(
            name="language.frameworks.python",
            value="python",
            source="test",
            metadata={"frameworks": ["FastAPI", "Django"]},
        ),
        Signal(
            name="dependencies.python",
            value="python",
            source="test",
            metadata={"packages": ["fastapi", "sqlalchemy", "alembic", "uvicorn", "pydantic"]},
        ),
        Signal(
            name="dependencies.node",
            value="node",
            source="test",
            metadata={"packages": ["express", "react", "redux", "webpack"]},
        ),
        Signal(
            name="build.python",
            value="python",
            source="test",
            metadata={"commands": ["python -m pytest"]},
        ),
        Signal(
            name="build.node",
            value="npm",
            source="test",
            metadata={"commands": ["npm test"]},
        ),
    ]

    comprehensive = PromptBuilder()
    conciseness = PromptBuilder(style="concise")

    full_section = comprehensive.render_sections(manifest, signals, ["features"])["features"].body
    concise_section = conciseness.render_sections(manifest, signals, ["features"])["features"].body

    full_bullets = [line for line in full_section.splitlines() if line.startswith("- ")]
    concise_bullets = [line for line in concise_section.splitlines() if line.startswith("- ")]

    assert len(full_bullets) >= len(concise_bullets)
    assert len(concise_bullets) <= 4


def test_architecture_section_includes_sequence_diagram(tmp_path: Path) -> None:
    repo = tmp_path / 'repo'
    repo.mkdir()
    _seed_repo(repo)

    manifest = RepoScanner().scan(str(repo))

    api_signal = Signal(
        name='architecture.api',
        value='GET /login',
        source='structure',
        metadata={
            'framework': 'FastAPI',
            'method': 'GET',
            'path': '/login',
            'sequence': [
                {'from': 'Client', 'to': 'FastAPI endpoint', 'message': 'GET /login'},
                {'from': 'FastAPI endpoint', 'to': 'External service', 'message': 'External HTTP call'},
                {'from': 'External service', 'to': 'FastAPI endpoint', 'message': 'Response'},
                {'from': 'FastAPI endpoint', 'to': 'Client', 'message': 'Response'},
            ],
        },
    )
    module_signal = Signal(
        name='architecture.modules',
        value='modules',
        source='structure',
        metadata={
            'modules': [
                {'name': 'src', 'files': 2, 'roles': ['src']},
                {'name': 'tests', 'files': 1, 'roles': ['test']},
            ]
        },
    )

    builder = PromptBuilder()
    sections = builder.render_sections(
        manifest,
        signals=[api_signal, module_signal],
        sections=['architecture'],
    )

    architecture = sections['architecture'].body
    assert 'sequenceDiagram' in architecture
    assert 'GET /login' in architecture
