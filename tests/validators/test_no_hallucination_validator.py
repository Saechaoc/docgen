"""Unit tests for the no-hallucination validator."""

from __future__ import annotations

from docgen.models import RepoManifest, Signal
from docgen.prompting.builder import Section
from docgen.validators import (
    NoHallucinationValidator,
    ValidationContext,
    build_evidence_index,
)


def _manifest() -> RepoManifest:
    return RepoManifest(root="/repo", files=[])


def test_validator_accepts_grounded_sentences() -> None:
    signals = [
        Signal(name="language.all", value="Python", source="language", metadata={"languages": ["Python"]}),
        Signal(name="entrypoint.cli", value="uvicorn", source="entrypoint", metadata={"command": "uvicorn app:app"}),
    ]
    sections = {
        "quickstart": Section(
            name="quickstart",
            title="Quick Start",
            body="1. Create a virtual environment (matches PyCharm settings)\n\n```bash\npython -m venv .venv\n```\n\n2. Run project commands discovered by analyzers\n\n```bash\npython -m pip install -r requirements.txt\nuvicorn app:app\n```",
            metadata={
                "steps": [
                    {
                        "title": "Create a virtual environment (matches PyCharm settings)",
                        "commands": ["python -m venv .venv"],
                    },
                    {
                        "title": "Run project commands discovered by analyzers",
                        "commands": ["python -m pip install -r requirements.txt", "uvicorn app:app"],
                    },
                ],
                "context": ["This project exposes a FastAPI app via uvicorn."],
                "evidence": {"signals": ["language.all", "entrypoint.cli"], "context_chunks": 1},
            },
        )
    }
    context = ValidationContext(
        manifest=_manifest(),
        signals=signals,
        sections=sections,
        evidence=build_evidence_index(signals, sections),
    )
    validator = NoHallucinationValidator()

    issues = validator.validate(context)

    assert issues == []


def test_validator_flags_sentences_without_evidence() -> None:
    signals = [Signal(name="language.all", value="Python", source="language", metadata={})]
    sections = {
        "features": Section(
            name="features",
            title="Key Features",
            body="- Offers zero-downtime quantum teleportation.",
            metadata={
                "context": [],
                "evidence": {"signals": ["language.all"], "context_chunks": 0},
            },
        )
    }
    context = ValidationContext(
        manifest=_manifest(),
        signals=signals,
        sections=sections,
        evidence=build_evidence_index(signals, sections),
    )
    validator = NoHallucinationValidator()

    issues = validator.validate(context)

    assert len(issues) == 1
    assert issues[0].section == "features"
    assert "Missing evidence" in issues[0].detail


def test_validator_handles_plural_tokens() -> None:
    signals = [Signal(name="pattern.container", value="container", source="pattern", metadata={})]
    sections = {
        "deployment": Section(
            name="deployment",
            title="Deployment",
            body="Containers are orchestrated via a lightweight runtime layer.",
            metadata={
                "context": [],
                "evidence": {"signals": ["pattern.container"], "context_chunks": 0},
            },
        )
    }
    context = ValidationContext(
        manifest=_manifest(),
        signals=signals,
        sections=sections,
        evidence=build_evidence_index(signals, sections),
    )
    validator = NoHallucinationValidator()

    issues = validator.validate(context)

    assert issues == []


def test_validator_balanced_accepts_synonyms() -> None:
    signals = [
        Signal(name="dependencies.python", value="aws-dynamodb", source="deps", metadata={}),
    ]
    sections = {
        "architecture": Section(
            name="architecture",
            title="Architecture",
            body="The service persists state in DynamoDB tables.",
            metadata={"context": [], "evidence": {"signals": ["dependencies.python"], "context_chunks": 0}},
        )
    }
    context = ValidationContext(
        manifest=_manifest(),
        signals=signals,
        sections=sections,
        evidence=build_evidence_index(signals, sections),
    )
    validator = NoHallucinationValidator(mode="balanced")

    issues = validator.validate(context)

    assert issues == []



def test_validator_strict_requires_observed_terms() -> None:
    signals = [Signal(name="dependencies.python", value="terraform", source="deps", metadata={})]
    sections = {
        "deployment": Section(
            name="deployment",
            title="Deployment",
            body="Infrastructure changes are rolled out via Terraform.",
            metadata={"context": [], "evidence": {"signals": ["dependencies.python"], "context_chunks": 0}},
        )
    }
    context = ValidationContext(
        manifest=_manifest(),
        signals=signals,
        sections=sections,
        evidence=build_evidence_index(signals, sections),
    )
    validator = NoHallucinationValidator(mode="strict")

    issues = validator.validate(context)

    assert len(issues) == 1
    assert issues[0].section == "deployment"
