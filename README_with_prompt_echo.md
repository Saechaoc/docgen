# docgen
<!-- docgen:begin:badges -->
[![Build Status](https://img.shields.io/badge/build-pending-lightgrey.svg)](#)
[![Coverage](https://img.shields.io/badge/coverage-review--needed-lightgrey.svg)](#)
[![License](https://img.shields.io/badge/license-tbd-lightgrey.svg)](#)
<!-- docgen:end:badges -->

<!-- docgen:begin:toc -->
## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Build & Test](#build-test)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [License](#license)
<!-- docgen:end:toc -->

<!-- docgen:begin:intro -->
"Project: docgen
Section: Introduction

Document generation is a crucial aspect of software development, and docgen is a popular tool for generating documentation from a repository. This section will cover the key features and functionalities of docgen, including its role in the project, the main languages and frameworks used, and how it handles the repository's context.

**Project Structure & Module Organization**

docgen is designed to analyze the repository, build context, and generate the README locally. It handles Python, YAML, and other languages, making it versatile for various use cases.

**Main Languages and Frameworks**

docgen supports Python, YAML, and other languages. Python is the primary language, but YAML is also widely used for documentation. Docgen can generate documentation for various frameworks, such as Django, Flask, and Spring Boot.

**Project Structure & Module Organization**

docgen is designed to handle the repository's context. It mirrors the repository's directory structure, making it easy to update the README with relevant information.

**Commit & Pull Request Guidelines**

docgen follows conventional commits (feat:, fix:, docs:). It maintains a summary, testing notes, and links to relevant issues for review.

**Key Signals (JSON)**

{
  "frameworks": {},
  "languages": [
    "Python",
    "YAML"
  ],
  "project_name": "docgen"
}

**Context Snippets**

# Repository Guidelines

# Project Structure & Module Organization

docgen is designed to analyze the repository, build context, and generate the README locally. It handles Python, YAML, and other languages, making it versatile for various use cases.

# Commit & Pull Request Guidelines

docgen follows conventional commits (feat:, fix:, docs:). It maintains a summary, testing notes, and links to relevant issues for review.

# Markdown Body"
<!-- docgen:end:intro -->

## Features

<!-- docgen:begin:features -->
"Project: docgen
Section: Features
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Outline and emphasis:
- Provide 5-6 bullet points covering analyzers, templating, retrieval, LLM enforcement, post-processing, and publishing.
- Reference concrete modules or files when they exist.
Key signals (JSON):
{
  "all_items": [
    "**Repository manifest & caching** - `docgen/repo_scanner.py` walks the tree, respects ignore rules, and persists hashes for incremental runs.",
    "**Analyzer plugin system** - `docgen/analyzers/*` emit language, build, dependency, entrypoint, and structure signals for downstream prompting.",
    "**Template-driven prompting** - `docgen/prompting/builder.py` merges signals with Jinja templates and enforces markdown style presets.",
    "**Lightweight RAG index** - `docgen/rag/indexer.py` embeds repo snippets into `.docgen/embeddings.json` for section-scoped retrieval.",
    "**Local LLM enforcement** - `docgen/llm/runner.py` targets loopback runtimes (Model Runner, Ollama, llama.cpp) with token and temperature guards.",
    "**Post-processing contract** - `docgen/postproc/*` rebuild badges, ToC, lint markdown, validate links, and compute scorecards."
  ],
  "items": [
    "**Repository manifest & caching** - `docgen/repo_scanner.py` walks the tree, respects ignore rules, and persists hashes for incremental runs.",
    "**Analyzer plugin system** - `docgen/analyzers/*` emit language, build, dependency, entrypoint, and structure signals for downstream prompting.",
    "**Template-driven prompting** - `docgen/prompting/builder.py` merges signals with Jinja templates and enforces markdown style presets.",
    "**Lightweight RAG index** - `docgen/rag/indexer.py` embeds repo snippets into `.docgen/embeddings.json` for section-scoped retrieval.",
    "**Local LLM enforcement** - `docgen/llm/runner.py` targets loopback runtimes (Model Runner, Ollama, llama.cpp) with token and temperature guards.,
    "**Post-processing contract** - `docgen/postproc/*` rebuild badges, ToC, lint markdown, validate links, and compute scorecards."
  ]
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable. ## Commit & Pull Request Guidelines - Follow conventional commits (`feat:`, `fix:`, `docs:`); keep subject lines <=72 characters and explain broader scope in the body when multiple subsystems change. - Bundle related work into a single PR that includes a summary, testing notes, and links to relevant iss...
Return only the markdown content for this section, without extra commentary.
<!-- docgen:end:features -->

## Architecture

<!-- docgen:begin:architecture -->
- Use subsections: `### High-Level Flow`, `### Component Responsibilites`, `### Artifacts and Data Stores`.
- Add `### Pipeline Sequence (docgen init)`, `### Patch Sequence (docgen update)`, and `### API Signal Extraction`.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
Key signals (JSON):
{
  "artifacts": [],
  "diagram": "sequenceDiagram\n    participant FastAPI endpoint\n    participant Client\n    Client ->> FastAPI endpoint: GET /health\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /init\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST /update\n    FastAPI endpoint -->> Client: Response\n    Client ->> FastAPI endpoint: POST
<!-- docgen:end:architecture -->

## Quick Start

<!-- docgen:begin:quickstart -->
```
# Quick Start

# Install
uvicorn docgen.service.app:app --reload
uvicorn tests.analyzers.test_entrypoints:napp --reload
uvicorn tests.analyzers.test_structure:app --reload
python docgen/cli.py

# Run cli.py
python docgen/cli.py

# Document build steps here.
```
<!-- docgen:end:quickstart -->

## Configuration

<!-- docgen:begin:configuration -->
Project: docgen
Section: Configuration
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Outline and emphasis:
- Highlight key configuration files (e.g., `.docgen.yml`) and environment variables.
- Mention how users can toggle analyzers, templates, and publish modes.
Key signals (JSON):
{
  "all_files": [],
  "files": []
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable. # Commit & Pull Request Guidelines - Follow Conventional Commits (`feat:`, `fix:`, `docs:`); keep subject lines <=72 characters and explain broader scope in the body when multiple subsystems change. - Bundle related work into a single PR that includes a summary, testing notes, and links to relevant issues.
<!-- docgen:end:configuration -->

## Build & Test

<!-- docgen:begin:build_and_test -->
Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section: Build & Test
Write the markdown body for this section using only repository-derived facts.
Follow the requested outline, keep explanations crisp, and never invent commands or tools.
Key signals (JSON):
{
  "tools": {
    "generic": [
      "# Document build steps here."
    ]
  }
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Markdown:

Project: docgen
Section
<!-- docgen:end:build_and_test -->

## Deployment

<!-- docgen:begin:deployment -->
Project: docgen
Section: Deployment
Write the markdown body for this section using only repository-derived facts.

Follow the requested outline, keep explanations crisp, and never invent commands or tools.

Outline and emphasis:

- Explain automation or CI workflows that publish README updates.
- Mention container or packaging options if detected.
Key signals (JSON):
{
  "docker": false
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.

Return only the markdown content for this section, without extra commentary.
<!-- docgen:end:deployment -->

## Troubleshooting

<!-- docgen:begin:troubleshooting -->
Project: docgen
Section: Troubleshooting

Markdown body:

- Provide 4-5 actionable diagnostics tips, focusing on verbose logs, cache resets, and reruns after fixes.
Key signals (JSON):
{
  "all_items": [
    "Confirm dependencies are installed before running commands.",
    "Use `docgen update` after code changes to refresh sections automatically.",
    "Open an issue when docgen requires additional diagnostics in this section."
  ],
  "items": [
    "Confirm dependencies are installed before running commands.",
    "Use `docgen update` after code changes to refresh sections automatically.",
    "Open an issue when docgen requires additional diagnostics in this section."
  ]
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.
<!-- docgen:end:troubleshooting -->

## FAQ

<!-- docgen:begin:faq -->
{
  "qa": [
    {
      "answer": "Generated with `docgen init` and updated via `docgen update`.",
      "question": "How is this README maintained?"
    },
    {
      "answer": "File an issue or start a discussion in this repository.",
      "question": "Where do I report issues?"
    }
  ]
}
Context snippets:
- # Repository Guidelines ## Project Structure & Module Organization - `spec/spec.md` captures the end-to-end architecture, component contracts, and must be updated whenever responsibilities shift. - Place Python source in a `docgen/` package (create it when implementation starts) with clear submodules for orchestrator, analyzers, runners, and stores; avoid leaving logic in the repo root. - Mirror r...
- README slices under `tests/data/` and update them with helper scripts so diffs stay reviewable.
<!-- docgen:end:faq -->

## License

<!-- docgen:begin:license -->
Project: docgen
Section: License

**License:**

**Current Licensing Status:**

**License File:**

**Repository Structure:**

**Module Organization:**

**Commit & Pull Request Guidelines:**

Markdown:

```
# Repository Guidelines
# Project Structure & Module Organization
# # Repository Guidelines
# # Project Structure & Module Organization
# # # Repository Guidelines
# # # Project Structure & Module Organization
# # # # Repository Guidelines
# # # # Project Structure & Module Organization
# # # # # Repository Guidelines
# # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # # # # # Repository Guidelines
# # # #
<!-- docgen:end:license -->
