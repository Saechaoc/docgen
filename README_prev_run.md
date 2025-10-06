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
docgen is a local-first README generator for polyglot repositories built primarily with Python and YAML. It scans every tracked file, emits analyzer signals, retrieves grounded context, and drives a local LLM through templated sections to keep documentation accurate. The overview below captures the full pipeline so contributors understand the moving pieces before running `docgen init`. Refer to `spec/spec.md` for detailed architecture contracts and responsibilities.
<!-- docgen:end:intro -->

## Features

<!-- docgen:begin:features -->
- **Repository manifest & caching** - `docgen/repo_scanner.py` walks the tree, respects ignore rules, and persists hashes for incremental runs.
- **Analyzer plugin system** - `docgen/analyzers/*` emit language, build, dependency, entrypoint, and structure signals for downstream prompting.
- **Template-driven prompting** - `docgen/prompting/builder.py` merges signals with Jinja templates and enforces markdown style presets.
- **Lightweight RAG index** - `docgen/rag/indexer.py` embeds repo snippets into `.docgen/embeddings.json` for section-scoped retrieval.
- **Local LLM enforcement** - `docgen/llm/runner.py` targets loopback runtimes (Model Runner, Ollama, llama.cpp) with token and temperature guards.
- **Post-processing contract** - `docgen/postproc/*` rebuild badges, ToC, lint markdown, validate links, and compute scorecards.
- **Git-aware publishing** - `docgen/git/publisher.py` and `docgen/git/diff.py` map repo changes to sections and push commits or PRs.
- **Resilient CLI UX** - `docgen/cli.py` exposes `init`/`update` commands with verbose logging, dry-run previews, and validation toggles.
- Primary stack: Python, YAML
- Supported build tooling: generic
- Ready for continuous README generation via docgen.
<!-- docgen:end:features -->

## Architecture

<!-- docgen:begin:architecture -->
- Use subsections: `### High-Level Flow`, `### Component Responsibilities`, `### Artifacts and Data Stores`.
- Add `### Pipeline Sequence (docgen init)`, `### Patch Sequence (docgen update)`, and `### API Signal Extraction`.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting, LLM execution, and publishing.
- Include available Mermaid diagrams or tables when metadata provides them.
- Describe how the orchestrator coordinates scanning, analyzers, retrieval, prompting,
<!-- docgen:end:architecture -->

## Quick Start

<!-- docgen:begin:quickstart -->
Follow the steps below to get started:

`ash
uvicorn docgen.service.app:app --reload
uvicorn tests.analyzers.test_entrypoints:napp --reload
uvicorn tests.analyzers.test_structure:app --reload
python docgen/cli.py

# Document build steps here.
`
<!-- docgen:end:quickstart -->

## Configuration

<!-- docgen:begin:configuration -->
List configuration files or environment variables required to run the project.
<!-- docgen:end:configuration -->

## Build & Test

<!-- docgen:begin:build_and_test -->
**Generic**
- # Document build steps here.
<!-- docgen:end:build_and_test -->

## Deployment

<!-- docgen:begin:deployment -->
Outline deployment strategies or hosting targets here.
<!-- docgen:end:deployment -->

## Troubleshooting

<!-- docgen:begin:troubleshooting -->
- Confirm dependencies are installed before running commands.
- Use `docgen update` after code changes to refresh sections automatically.
- Open an issue when docgen requires additional diagnostics in this section.
<!-- docgen:end:troubleshooting -->

## FAQ

<!-- docgen:begin:faq -->
**Q: How is this README maintained?**
A: Generated with `docgen init` and updated via `docgen update`.

**Q: Where do I report issues?**
A: File an issue or start a discussion in this repository.
<!-- docgen:end:faq -->

## License

<!-- docgen:begin:license -->
Add licensing information once the project selects a license.
<!-- docgen:end:license -->
